# Claude Opus 5.5 (low): Identify Excessive or Duplicative Research Charges in Litigation Invoice

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json) · [GPT-6 Luna (xhigh) run](../gpt6luna-xhigh/README.md) · [All runs](../../README.md)

**Model:** `claude-opus-5-5`, reasoning effort `low`. **Run:** `20260926-202411`.

**Native grades:** Sonnet 4.6 passed 33 of 46 criteria; GPT-5.5 passed 37 of 46 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [research-charge-review-memo.docx](output/research-charge-review-memo.docx) ([read as Markdown](output/research-charge-review-memo.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | Issue 1: Identifies research charges exceed 12% cap (Section 6.2) | Pass | Pass |
| [C-002](#c-002) | Issue 1: Calculates net research percentage as approximately 13.56% | Pass | Pass |
| [C-003](#c-003) | Issue 1: Calculates gross research percentage as approximately 15.83% | **Fail** | **Fail** |
| [C-004](#c-004) | Issue 1: Notes no prior written approval from Marcus Holt for cap exceedance | Pass | Pass |
| [C-005](#c-005) | Issue 1: References Holt's June 28 email as notice to firm about cap | Pass | Pass |
| [C-006](#c-006) | Issue 1: Calculates 12% cap dollar amount as approximately $41,018 | **Fail** | **Fail** |
| [C-007](#c-007) | Issue 2: Identifies Diane Hargrove's partner research billing violation | Pass | Pass |
| [C-008](#c-008) | Issue 2: Identifies specific Hargrove research entries (July 9, 17, 30) | Pass | Pass |
| [C-009](#c-009) | Issue 2: Calculates Hargrove overcharge as approximately $1,925 | **Fail** | **Fail** |
| [C-010](#c-010) | Issue 2: Notes Hargrove's entries lack required exceptional circumstances notation | Pass | Pass |
| [C-011](#c-011) | Issue 2: Identifies Nathan Briggs's partner research billing violation | Pass | Pass |
| [C-012](#c-012) | Issue 2: Calculates Briggs overcharge as approximately $1,260 | **Fail** | Pass |
| [C-013](#c-013) | Issue 3: Identifies duplicative MTCA research across Takahashi and Wendt | Pass | Pass |
| [C-014](#c-014) | Issue 3: References specific duplicative MTCA entries | **Fail** | Pass |
| [C-015](#c-015) | Issue 3: Calculates recommended adjustment for duplicative MTCA research | Pass | Pass |
| [C-016](#c-016) | Issue 4: Identifies duplicative consequential/lost profits damages research | **Fail** | **Fail** |
| [C-017](#c-017) | Issue 4: Notes Osei's excessive hours (13.0 hrs) on one research topic | **Fail** | **Fail** |
| [C-018](#c-018) | Issue 5: Identifies duplicative economic loss rule research on July 12 | **Fail** | **Fail** |
| [C-019](#c-019) | Issue 5: Recommends adjustment for economic loss rule duplication | Pass | Pass |
| [C-020](#c-020) | Issue 6: Identifies duplicative spoliation/ESI sanctions research | Pass | Pass |
| [C-021](#c-021) | Issue 7: Flags Wendt's July 25 'get up to speed' entry as non-billable | Pass | Pass |
| [C-022](#c-022) | Issue 7: Flags Wendt's July 15 'familiarize' entry as non-billable | Pass | Pass |
| [C-023](#c-023) | Issue 7: Calculates total onboarding adjustment (~$2,677.50) | **Fail** | Pass |
| [C-024](#c-024) | Issue 8: Flags block-billed 'research and draft' entries under Section 6.5 | **Fail** | Pass |
| [C-025](#c-025) | Issue 8: Notes Section 6.5 requires 50% allocation to non-research | **Fail** | **Fail** |
| [C-026](#c-026) | Issue 9: Identifies Westlaw disbursement charge as prohibited | Pass | Pass |
| [C-027](#c-027) | Issue 9: Recommends $4,850 adjustment for Westlaw disbursement | Pass | Pass |
| [C-028](#c-028) | Issue 10: Identifies inter-matter duplicative MTCA research with DOE Matter | Pass | Pass |
| [C-029](#c-029) | Issue 10: Cites Section 6.6 for inter-matter research prohibition | Pass | Pass |
| [C-030](#c-030) | Issue 11: Identifies arithmetic error in research efficiency discount | Pass | Pass |
| [C-031](#c-031) | Issue 11: Calculates correct discount amount (~$8,115.68) | Pass | Pass |
| [C-032](#c-032) | Issue 12: Identifies duplicative unjust enrichment research (July 23-24) | Pass | Pass |
| [C-033](#c-033) | Issue 13: Flags July MTCA research as potentially duplicative of June work | **Fail** | **Fail** |
| [C-034](#c-034) | Issue 13: Acknowledges reply brief may justify some additional research | Pass | Pass |
| [C-035](#c-035) | Distractor 5: Does not flag litigation database hosting as improper | Pass | Pass |
| [C-036](#c-036) | Memo states correct invoice total amount | Pass | Pass |
| [C-037](#c-037) | Memo includes a summary table of all recommended adjustments | Pass | Pass |
| [C-038](#c-038) | Memo includes severity assessments for identified issues | **Fail** | **Fail** |
| [C-039](#c-039) | Issue 2: Cites Section 6.3 for partner research restriction | Pass | Pass |
| [C-040](#c-040) | Issue 3: Cites Section 6.4 for duplicative MTCA research | Pass | Pass |
| [C-041](#c-041) | Issue 7: Cites Section 4.3 for onboarding/get-up-to-speed entries | Pass | Pass |
| [C-042](#c-042) | Issue 9: Cites Section 9.3 for Westlaw disbursement violation | Pass | Pass |
| [C-043](#c-043) | Summary table total reflects aggregation of individual adjustments | Pass | Pass |
| [C-044](#c-044) | Issue 4: Recommends dollar adjustment for damages research duplication | Pass | Pass |
| [C-045](#c-045) | Issue 6: Recommends dollar adjustment for spoliation/ESI duplication | Pass | Pass |
| [C-046](#c-046) | Osei's July 19 background research flagged as potentially non-billable | Pass | Pass |

## Judge reasoning

### C-001

Issue 1: Identifies research charges exceed 12% cap (Section 6.2) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L18))

- **Sonnet 4.6: Pass.** The memo explicitly identifies that research charges exceed the 12% cap in Section 6.2. In Section 2 (Governing Standards), it quotes §6.2 requiring research ≤ 12% of monthly professional fees. In Section 1 (Executive Summary), it states 'the firm itself reports research at 13.56% of fees, which is over the 12% cap in §6.2.' Section 3.7 provides a detailed recalculation showing that before adjustments, research exceeds the cap, and explains how after entry-level adjustments the cap is met. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The memo explicitly states that research exceeded the 12% cap, including in the Executive Summary ('over the 12% cap in §6.2') and provides a research cap recalculation citing Guidelines §6.2.

### C-002

Issue 1: Calculates net research percentage as approximately 13.56% ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L26))

- **Sonnet 4.6: Pass.** The criterion requires the memo to state that net research charges ($46,372.50) as a percentage of total fees ($341,820.50) is approximately 13.56%. The memo does mention '13.56%' in the executive summary: 'Even after that discount, the firm itself reports research at 13.56% of fees, which is over the 12% cap in §6.2.' This matches the required percentage. However, the memo attributes this figure to what 'the firm itself reports' rather than explicitly tying it to $46,372.50 / $341,820.50. The criterion asks whether the memo 'calculates or states' this percentage, and the memo does state 13.56% in the context of net research as a percentage of fees. This satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly states that, after the research discount, the firm reports research at 13.56% of fees, and later references the $341,820.50 net-fee denominator. This satisfies the requirement to identify the net research percentage as approximately 13.56%.

### C-003

Issue 1: Calculates gross research percentage as approximately 15.83% ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L34))

- **Sonnet 4.6: Fail.** The memo does not explicitly calculate or state that gross research charges ($54,104.50) as a percentage of total fees ($341,820.50) is approximately 15.83%. The memo mentions that the firm's own Summary calculates research at 13.56% of fees, and separately calculates research as 22.3% of itemized fees. It also notes the cap denominator issue with $341,820.50 but never computes the 15.83% figure from $54,104.50 / $341,820.50.
- **GPT-5.5: Fail.** The memo references the $54,104.50 research base and the $341,820.50 net-fee denominator, but it does not calculate or state the gross research percentage of approximately 15.83%. Instead, it states 13.56% after discount and other alternative percentages.

### C-004

Issue 1: Notes no prior written approval from Marcus Holt for cap exceedance ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L42))

- **Sonnet 4.6: Pass.** The memo explicitly states in the Executive Summary: 'Even after that discount, the firm itself reports research at 13.56% of fees, which is over the 12% cap in §6.2. No written approval was requested, although your email specifically asked for it.' This directly addresses the lack of prior written approval from the DGC (Marcus Holt) to exceed the 12% research cap required under §6.2.
- **GPT-5.5: Pass.** The memo expressly states that the research charges exceeded the 12% cap and that no written approval was requested, while also identifying the requirement for prior DGC approval under Guidelines §6.2. The memo is addressed to Marcus Holt, Deputy General Counsel, satisfying the criterion.

### C-005

Issue 1: References Holt's June 28 email as notice to firm about cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L50))

- **Sonnet 4.6: Pass.** The memo explicitly references Marcus Holt's June 28, 2024 email to Diane Hargrove in multiple places. In Section 1 (Executive Summary), it states 'The invoice has the problems you warned about in your June 28 email, and some new ones.' In Section 3.2, it states 'the firm has not delineated distinct sub-issues for any of these pairs, even though your June 28 email asked it to.' The email is clearly referenced as prior notice to the firm about research billing compliance.
- **GPT-5.5: Pass.** The memo expressly references Marcus Holt's June 28, 2024 email to Diane Hargrove about research billing, notes that the July invoice had the problems warned about in that email, and ties the email to the 12% research cap/compliance issue by stating no written approval was requested despite the email asking for it.

### C-006

Issue 1: Calculates 12% cap dollar amount as approximately $41,018 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L58))

- **Sonnet 4.6: Fail.** The criterion requires the memo to calculate or state that the 12% cap amount is approximately $41,018 (12% of $341,820.50 = $41,018.46). The agent's memo instead calculates the 12% cap as $24,747.85 (12% of $206,232.10, the adjusted net professional fees after all adjustments). The memo does not mention $41,018 or calculate 12% of $341,820.50. The agent used a different denominator for the cap calculation. Therefore, the criterion is not satisfied.
- **GPT-5.5: Fail.** The memo does not state the 12% cap as approximately $41,018 based on $341,820.50. Instead, it recalculates the cap using adjusted net professional fees of $206,232.10 and states a cap of $24,747.85, while only mentioning $341,820.50 as the firm's denominator without computing 12% of it.

### C-007

Issue 2: Identifies Diane Hargrove's partner research billing violation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L66))

- **Sonnet 4.6: Pass.** The memo identifies Diane Hargrove's partner research billing violations in Section 3.1. It flags lines 24 (1.8h, $1,611.00), 51 (2.2h, $1,969.00), and 92 (1.5h, $1,342.50) as partner research entries billed at full partner rates without the required notation, violating §6.3. The total hours for Hargrove are 1.8+2.2+1.5=5.5 hours. The memo recommends disallowing L24 and reducing L51 and L92. The criterion requires identifying that Hargrove billed 5.5 hours of research at her partner rate violating §6.3, which the memo does (though it doesn't explicitly state her rate as $895/hr, it does flag the violation clearly). The criterion is satisfied.
- **GPT-5.5: Pass.** The memo flags Hargrove's partner research under §6.3, listing three Hargrove research entries totaling 5.5 hours (1.8 + 2.2 + 1.5) billed at her partner rate of $895/hr, and recommends disallowance/reduction because partners may not bill research without the required notation.

### C-008

Issue 2: Identifies specific Hargrove research entries (July 9, 17, 30) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L74))

- **Sonnet 4.6: Pass.** The memo explicitly identifies all three of Hargrove's research entries: July 9 (1.8 hrs, MTCA preemption/contractor defense, Line 24), July 17 (2.2 hrs, Thompson v. Pacific Envtl. Corp. standard of care, Line 51), and July 30 (1.5 hrs, trial strategy considerations/jury verdict trends, Line 92). All three are listed in Section 3.1 with their dates, hours, and recommended adjustments. This clearly satisfies the criterion of identifying at least two of the three entries.
- **GPT-5.5: Pass.** The memo specifically identifies all three Hargrove research entries: July 9 (1.8 hrs), July 17 (2.2 hrs), and July 30 (1.5 hrs). This exceeds the requirement of at least two entries.

### C-009

Issue 2: Calculates Hargrove overcharge as approximately $1,925 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L82))

- **Sonnet 4.6: Fail.** The criterion requires the memo to calculate the Hargrove overcharge as approximately $1,925 (5.5 hrs × $895 = $4,922.50 billed vs. 5.5 hrs × $545 = $2,997.50; difference = $1,925.00), or alternatively recommend the full $4,922.50 be written off. Looking at the agent's output, Hargrove's research entries (L24 and L92) are handled as follows: L24 is disallowed in full ($1,611.00) under §§6.3 and 6.4, and L92 is reduced to $545/hr with a reduction of ($525.00). L51 is reduced to $545/hr with a reduction of ($770.00). The memo does not calculate a combined Hargrove overcharge of approximately $1,925 based on 5.5 hours at the difference between $895 and $545. Instead, it treats the entries individually and differently (some disallowed, some reduced). The specific calculation of $1,925 as the Hargrove overcharge is not present in the memo.
- **GPT-5.5: Fail.** The memo identifies Hargrove research entries totaling 5.5 hours and calculates some dollar adjustments, but it does not calculate the expected overcharge of approximately $1,925 based on reducing all 5.5 hours from $895/hr to $545/hr. Nor does it recommend writing off the full $4,922.50; instead it disallows/reduces selected entries totaling a different amount.

### C-010

Issue 2: Notes Hargrove's entries lack required exceptional circumstances notation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L90))

- **Sonnet 4.6: Pass.** The memo explicitly notes in Section 3.1 that partner research entries lack the required notation. For example, regarding Hargrove L51: 'Thompson v. Pacific Envtl. Corp. standard of care; no notation' and Hargrove L92: 'Trial strategy considerations / jury verdict trends; weak fit with the definition of legal research; no notation'. The memo also states in the governing standards table that §6.3 requires 'a notation explaining why it could not be delegated' and that 'Without the notation, the entry is automatically reduced to $545.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly states that the partner research entries, including Hargrove’s RES-coded entries, lack the notation required by §6.3, and specifically notes Hargrove lines 51 and 92 as having “no notation.”

### C-011

Issue 2: Identifies Nathan Briggs's partner research billing violation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L98))

- **Sonnet 4.6: Pass.** The memo clearly identifies Nathan Briggs as a partner billing research at full partner rates. In Section 3.1, the memo lists multiple Briggs entries (L7: 2.5h at $1,812.50; L41: 3.0h at $2,175.00; L74: 1.5h at $1,087.50; L92: 1.5h at $1,342.50) totaling 8.5 hours, all flagged as violating §6.3 (partner research billed at full partner rates without required notation). The criterion asks whether Briggs's 7.0 hours of partner research billing violation is identified. The memo does identify Briggs's partner research billing violations under §6.3, though the total hours identified (8.5h across four entries) differs from the criterion's stated 7.0 hours. The criterion says PASS if the memo identifies that Briggs billed research at his partner rate violating §6.3 - the memo clearly does this, flagging multiple Briggs entries for this exact violation. The hour discrepancy (8.5 vs 7.0) may reflect different invoice data, but the core violation is clearly identified.
- **GPT-5.5: Pass.** The memo expressly flags Nathan Briggs under “Partner research (§6.3)” with three research entries totaling 7.0 hours (2.5 + 3.0 + 1.5) billed at $725/hr, and recommends disallowance/reduction for violating §6.3/§6.4.

### C-012

Issue 2: Calculates Briggs overcharge as approximately $1,260 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L106))

- **Sonnet 4.6: Fail.** The criterion requires the memo to calculate the Briggs overcharge as approximately $1,260 (7.0 hrs × $725 = $5,075 billed vs. 7.0 hrs × $545 = $3,815; difference = $1,260), or alternatively recommend the full $5,075 be written off. Looking at the agent's memo, Briggs's research entries (L7, L41, L74) are disallowed in full under §§6.3 and 6.4 (duplicative research), and L51 is not a Briggs entry. The memo does not calculate a specific ~$1,260 overcharge for Briggs based on the rate differential (full partner rate vs. senior associate rate of $545). Instead, it disallows the entries entirely or reduces them differently. There is no calculation of 7.0 hrs × $725 vs. 7.0 hrs × $545 yielding ~$1,260 anywhere in the memo.
- **GPT-5.5: Pass.** The memo identifies Briggs’s partner research entries totaling 7.0 hours at $725/hour and recommends disallowing them in full: $1,812.50 + $2,175.00 + $1,087.50 = $5,075. This satisfies the criterion’s alternative of recommending the full $5,075 be written off.

### C-013

Issue 3: Identifies duplicative MTCA research across Takahashi and Wendt ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L114))

- **Sonnet 4.6: Pass.** The memo explicitly identifies in Section 3.2 that both Takahashi and Wendt billed for overlapping MTCA contractor liability/SJ standards research, with Takahashi L1 and L6 allowed as the most junior qualified researcher, while Wendt L2 ($1,360.00) and L15 ($1,700.00) are disallowed under §6.4. The memo also references Hargrove L24 as duplicating MTCA preemption/contractor defense research by Takahashi. This clearly identifies the duplicative MTCA research across multiple timekeepers including Takahashi and Wendt, citing Section 6.4.
- **GPT-5.5: Pass.** The memo expressly identifies overlapping MTCA contractor liability / summary judgment research by Kenji Takahashi and Tyler Wendt in July 2024, allows Takahashi L1/L6 as the most junior researcher, disallows Wendt L2/L15, and cites Guidelines §6.4 on duplicative research.

### C-014

Issue 3: References specific duplicative MTCA entries ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L122))

- **Sonnet 4.6: Fail.** The criterion requires the memo to reference at least Takahashi's July 1 (4.5 hrs) entry AND either Wendt's July 1 (3.2 hrs) or July 5 (4.0 hrs) entry as duplicative MTCA entries. The memo does reference Takahashi L1 (July 1, 4.5 hrs) in Section 3.2 and Section 3.6 as allowed research on MTCA contractor liability. However, the duplicative entries identified for MTCA are Wendt L2 ($1,360.00) and L15 ($1,700.00), not Wendt's July 1 (3.2 hrs) or July 5 (4.0 hrs) entries specifically. The memo does not identify Wendt's July 1 (3.2 hrs) or July 5 (4.0 hrs) entries by those specific dates/hours as duplicative. The Wendt entries flagged are L2 and L15 without specifying those particular dates. The criterion requires specific entry pairs to be identified, and while Takahashi's July 1 entry is referenced, the corresponding Wendt July 1 or July 5 entries are not specifically identified as duplicative with those particular dates and hours.
- **GPT-5.5: Pass.** The memo identifies the MTCA contractor liability/SJ research as duplicative, allowing Takahashi L1/L6 and disallowing Wendt L2 and L15. It also elsewhere specifies Takahashi L1 as the July 1, 4.5-hour MTCA entry. Wendt L2/L15 correspond to the July 1 3.2-hour and/or July 5 4.0-hour entries, so the required duplicative MTCA entries are referenced.

### C-015

Issue 3: Calculates recommended adjustment for duplicative MTCA research ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L130))

- **Sonnet 4.6: Pass.** In Section 3.2, the memo explicitly identifies MTCA contractor liability / SJ standards as a duplicative research issue and disallows Wendt L2 ($1,360.00) and L15 ($1,700.00), totaling $3,060.00 in reductions for duplicative MTCA research by Wendt. This satisfies the criterion of recommending a dollar adjustment for duplicative MTCA research.
- **GPT-5.5: Pass.** The memo specifically identifies duplicative MTCA contractor liability / summary judgment research and recommends disallowing Wendt L2 ($1,360) and L15 ($1,700), for a total reduction of $3,060, satisfying the criterion.

### C-016

Issue 4: Identifies duplicative consequential/lost profits damages research ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L138))

- **Sonnet 4.6: Fail.** The criterion requires the memo to identify that consequential damages and lost profits research was duplicated across timekeepers, specifically referencing Osei's research on July 8 (7.5 hrs) and/or July 10 (5.5 hrs) on consequential damages, and Wendt (4.5 hrs, July 18) and/or Takahashi (3.5 hrs, July 18) on lost profits, noting that lost profits is a subset of consequential damages. The memo does have entries for 'Consequential damages (WA)' (Osei L20 allowed, Takahashi L11 disallowed) and 'Lost profits damages (WA)' (Takahashi L56 allowed, Wendt L55 disallowed). However, the memo treats these as separate issues rather than noting that lost profits is a subset of consequential damages. The specific dates and hours mentioned in the criterion (Osei July 8 7.5 hrs, July 10 5.5 hrs; Wendt 4.5 hrs July 18; Takahashi 3.5 hrs July 18) do not match the line references in the memo. Most critically, the memo does not identify that lost profits is a subset of consequential damages, which is a key requirement of the criterion. The criterion specifically requires noting this relationship to establish the duplication. The memo treats them as separate issues and does not make this connection.
- **GPT-5.5: Fail.** The memo flags separate duplications for consequential damages and lost profits research, including Osei on consequential damages and Wendt/Takahashi on lost profits. However, it does not identify the cross-duplication between consequential damages and lost profits research or note that lost profits is a subset of consequential damages, as the criterion specifically requires.

### C-017

Issue 4: Notes Osei's excessive hours (13.0 hrs) on one research topic ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L146))

- **Sonnet 4.6: Fail.** The memo does mention Osei L20 (consequential damages, WA) in the duplicative research table, but only to note that Takahashi L11 is disallowed as duplicative while Osei L20 ($2,212.50) is allowed as the most junior qualified researcher. The memo does not flag that Osei spent approximately 13 hours total (7.5 hrs on July 8 + 5.5 hrs on July 10) on Washington consequential damages law as excessive in terms of hours. The criterion specifically requires noting the excessive hours on this single topic, which the memo does not do.
- **GPT-5.5: Fail.** The memo mentions Osei's consequential damages research only as an allowed entry in a duplicative-research table and does not flag that Osei spent approximately 13 hours across July 8 and July 10 on essentially one Washington consequential damages research question, nor characterize those hours as excessive.

### C-018

Issue 5: Identifies duplicative economic loss rule research on July 12 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L154))

- **Sonnet 4.6: Fail.** The criterion requires identification of same-day duplication on July 12 specifically, with Kenji Takahashi (6.0 hrs) and Amara Osei (4.5 hrs) both researching the Washington economic loss rule. The memo does identify economic loss rule research as duplicative (Section 3.2, 'Economic loss rule (WA remediation contracts)'), listing Osei L29, L38 as allowed and Takahashi L37 as disallowed. However, the memo does not specify that this occurred on July 12, does not mention the specific hours (6.0 hrs for Takahashi and 4.5 hrs for Osei), and does not highlight the same-day nature of the duplication. The criterion specifically requires identification of the July 12 same-day duplication with those specific timekeepers and hours. The memo's treatment is more general and references different line numbers (L29, L38, L37) without specifying July 12 or the 6.0/4.5 hour breakdown on that specific date.
- **GPT-5.5: Fail.** The memo flags economic loss rule research as duplicative between Osei and Takahashi under §6.4, but it does not identify the required same-day July 12 duplication, the specific 6.0 and 4.5 hour entries, or the total 10.5 hours on that topic in one day.

### C-019

Issue 5: Recommends adjustment for economic loss rule duplication ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L162))

- **Sonnet 4.6: Pass.** The memo's Section 3.2 includes a row for 'Economic loss rule (WA remediation contracts)' where Osei L29, L38 ($2,950.00) are allowed as the most junior qualified researcher, and Takahashi L37 is disallowed with a reduction of ($2,040.00). This is a dollar adjustment recommended for the duplicative economic loss rule research. The criterion asks for at minimum a disallowance of Osei's 4.5 hours at $295/hr = $1,327.50, but the memo instead disallows Takahashi's overlapping entry ($2,040.00) while keeping Osei's entries. The criterion says 'Osei's 4.5 hours at $295/hr = $1,327.50 should be recommended for disallowance or a comparable amount.' The memo recommends a comparable amount ($2,040.00) for disallowance of the duplicative entry (Takahashi's), which satisfies the criterion of recommending a dollar adjustment for the duplicative economic loss rule research.
- **GPT-5.5: Pass.** The memo specifically identifies duplicative “Economic loss rule (WA remediation contracts)” research in Section 3.2 and recommends a dollar reduction of $2,040.00 for Takahashi L37. Although it allows Osei’s entries rather than disallowing Osei’s 4.5 hours, it still recommends a comparable dollar adjustment for the duplicative economic loss rule research.

### C-020

Issue 6: Identifies duplicative spoliation/ESI sanctions research ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L170))

- **Sonnet 4.6: Pass.** The memo does identify duplicative spoliation/ESI sanctions research. In Section 3.1, it flags Briggs L7 (7/2, 2.5 hrs) and L74 (7/24, 1.5 hrs) as duplicating Takahashi L86 on spoliation/ESI sanctions. In Section 3.2, it shows the spoliation/ESI sanctions cluster: Takahashi L86 is allowed as the most junior qualified researcher, while Wendt L87 is disallowed as duplicative. However, the criterion specifically requires referencing 'July 29 entries by Takahashi (4.3 hrs) and Wendt (2.8 hrs).' The memo references 'Takahashi L86' and 'Wendt L87' but does not specify July 29 dates or the specific hour counts of 4.3 hrs and 2.8 hrs. The memo does identify the duplication between Takahashi and Wendt on spoliation/ESI, and also identifies Briggs's July 2 and July 24 entries as duplicative. The criterion says PASS if the memo identifies duplicative research referencing 'at least' those entries as duplicative of each other and/or of Briggs's earlier entries. The memo does reference Takahashi L86 and Wendt L87 as duplicative of each other, and Briggs L7 (7/2) and L74 (7/24) as also duplicative. The line numbers L86 and L87 correspond to the July 29 entries described in the criterion. The criterion is satisfied even if exact dates/hours aren't spelled out, since the line references and the duplication finding are clearly present.
- **GPT-5.5: Pass.** The memo identifies duplicative spoliation/ESI sanctions research. It specifically lists Briggs’s July 2 and July 24 entries as duplicative, and in Section 3.2 treats Takahashi L86 as the allowed spoliation/ESI sanctions research while disallowing Wendt L87 as duplicative, with Briggs L7 and L74 also noted. Although it does not spell out the July 29 date or hours in that table, it clearly references the relevant Takahashi and Wendt entries and identifies the duplication.

### C-021

Issue 7: Flags Wendt's July 25 'get up to speed' entry as non-billable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L178))

- **Sonnet 4.6: Pass.** In Section 3.3 of the memo, the agent explicitly flags Wendt L78 (3.8 hours, $1,615.00) with the description 'Review file materials and research background... get up to speed on technical remediation issues' as non-billable background/familiarization research under §§4.3 and 6.4, recommending a reduction of ($1,615.00). The date listed is line 78, and while the memo uses line numbers rather than dates, the description, timekeeper (Wendt), hours (3.8h), and amount ($1,615.00) all match the criterion's description of the July 25 entry. The entry is clearly identified and flagged as non-billable.
- **GPT-5.5: Pass.** The memo specifically flags Wendt’s 3.8-hour entry with description “Review file materials and research background... get up to speed on technical remediation issues” in Section 3.3 as background/familiarization research, cites §§4.3 and 6.4, and recommends a $1,615 reduction as non-billable.

### C-022

Issue 7: Flags Wendt's July 15 'familiarize' entry as non-billable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L186))

- **Sonnet 4.6: Pass.** In Section 3.3, the memo flags Line 42 as Wendt (2.5 h) with description 'Research background on Washington environmental regulatory framework; familiarize with MTCA amendments' and recommends a reduction of ($1,062.50) under §§4.3, 6.4. The date listed is not explicitly '7/15' in the table, but the entry matches the criterion's description (Wendt, 2.5 hrs, $1,062.50, 'familiarize with MTCA amendments'). The memo identifies this as non-billable background/familiarization research under §§4.3 and 6.4. This satisfies the criterion.
- **GPT-5.5: Pass.** The memo flags Wendt’s 2.5-hour, $1,062.50 entry describing background research and “familiarize with MTCA amendments” in Section 3.3 as background/familiarization research, cites §§4.3 and 6.4, and recommends disallowing it as non-billable onboarding/background work.

### C-023

Issue 7: Calculates total onboarding adjustment (~$2,677.50) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L194))

- **Sonnet 4.6: Fail.** The criterion requires the memo to calculate the onboarding/familiarization adjustment as approximately $2,677.50 (6.3 hrs × $425/hr), reflecting disallowance of Wendt's July 15 (2.5 hrs) and July 25 (3.8 hrs) entries. The agent's memo instead calculates a total of ($4,152.50) for background/familiarization research across three entries: Wendt L42 (2.5h, $1,062.50), Osei L60 (5.0h, $1,475.00), and Wendt L78 (3.8h, $1,615.00). The individual amounts don't match the criterion's expected ~$2,677.50 figure, and the total is $4,152.50 rather than ~$2,677.50. The criterion specifically asks for ~$2,677.50 reflecting only Wendt's two entries (July 15 and July 25), but the agent includes Osei's entry as well and uses different per-hour rates. The agent does calculate dollar adjustments for these entries, but the amounts differ significantly from what the criterion specifies.
- **GPT-5.5: Pass.** The memo identifies the getting-up-to-speed/familiarization entries and assigns dollar reductions to Wendt’s 2.5-hour entry ($1,062.50) and 3.8-hour entry ($1,615.00), which together equal $2,677.50. Although it also includes an additional Osei background-research entry in the subtotal, the required Wendt onboarding adjustment is calculated.

### C-024

Issue 8: Flags block-billed 'research and draft' entries under Section 6.5 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L202))

- **Sonnet 4.6: Fail.** The memo does address block-billed entries under Section 6.5 in section 3.5. It mentions 'Osei L10, L20, L47; Takahashi L37; Wendt L33' as entries that combine research with memo or brief preparation without allocating time, and cites §6.5(ii). However, the criterion specifically requires reference to at least one of: Osei July 3 (6.0 hrs), Osei July 8 (7.5 hrs), or Osei July 16 (3.5 hrs). The memo references Osei entries by line number (L10, L20, L47) but does not specify dates or hours that match the three specific entries listed in the criterion. Without being able to confirm that L10, L20, or L47 correspond to July 3, July 8, or July 16 entries with those specific hour counts, and given that the criterion explicitly names those dates and hours as the reference points, the memo does not clearly satisfy the requirement. The memo's block-billing discussion is general and uses line numbers rather than the specific dated entries the criterion requires.
- **GPT-5.5: Pass.** The memo expressly flags block-billed entries under §6.5, stating that Osei L10, L20, and L47 combine research with memo/brief preparation without allocating time and should be counted in full as research. These correspond to the required Osei research-and-draft entries, satisfying the criterion.

### C-025

Issue 8: Notes Section 6.5 requires 50% allocation to non-research ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L210))

- **Sonnet 4.6: Fail.** The memo's Section 3.5 discusses block-billed entries under §6.5, but it only states that entries combining research with other tasks 'do not allocate time' and therefore 'are counted in full as research' per §6.5(ii). The memo does not articulate any requirement that block-billed entries must allocate at least 50% of time to the non-research component, nor does it mention any 'cap rate' reduction tied to a 50% allocation threshold. The criterion specifically requires the memo to explain this 50% allocation requirement, which is absent from the output.
- **GPT-5.5: Fail.** The memo discusses Section 6.5 and states that unallocated block-billed research/drafting entries count entirely as research, but it does not articulate the specific requirement that at least 50% of the time must be allocated to the non-research component or else the entire entry is reduced to the research cap rate.

### C-026

Issue 9: Identifies Westlaw disbursement charge as prohibited ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L218))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the $4,850.00 Westlaw charge in Section 4 ('Research-Related Disbursement: Westlaw (§9.3)'), citing Section 9.3 and the Engagement Letter §5 as prohibiting the charge, and recommends disallowing it in full. It also appears in the summary table as a disallowed disbursement.
- **GPT-5.5: Pass.** The memo explicitly identifies D-1 as a “Westlaw research charges — July 2024” disbursement of $4,850.00, cites Guidelines §9.3 and the engagement letter, states that Westlaw/Lexis charges are included in hourly rates and prohibited, and recommends disallowing the charge in full.

### C-027

Issue 9: Recommends $4,850 adjustment for Westlaw disbursement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L226))

- **Sonnet 4.6: Pass.** The memo explicitly recommends a $4,850.00 disallowance for the Westlaw disbursement in Section 4 ('Disallow in full') and lists it in the summary table in Section 7 as '(\ $4,850.00)'. This matches the criterion exactly.
- **GPT-5.5: Pass.** The memo explicitly identifies the Westlaw research charges as an improper disbursement and recommends disallowing/reducing the invoice by $4,850.00 in multiple places, including the executive summary table, Section 4, and the adjustment summary.

### C-028

Issue 10: Identifies inter-matter duplicative MTCA research with DOE Matter ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L234))

- **Sonnet 4.6: Pass.** Section 3.6 of the memo explicitly identifies the inter-matter duplication between the Cascade invoice and the DOE Matter invoice (HL-TV-2024-REG-0731), citing Takahashi's MTCA research on July 1 (L1, 4.5h) and July 2 (L6, 5.0h) on the Cascade invoice overlapping with corresponding DOE invoice entries on the same dates, and cites §6.6 as the governing provision. The memo recommends disallowing the four overlapping DOE entries totaling $3,400.00.
- **GPT-5.5: Pass.** The memo expressly identifies inter-matter duplication between Kenji Takahashi’s July 1–2 Cascade MTCA research and similar MTCA research billed on the separate DOE Matter invoice HL-TV-2024-REG-0731, cites Guidelines §6.6, and recommends disallowing the overlapping DOE entries. Although it appears to total the DOE overlap as $3,400 rather than expressly saying 12.5 hours, the cross-matter duplicative MTCA research issue is clearly identified.

### C-029

Issue 10: Cites Section 6.6 for inter-matter research prohibition ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L242))

- **Sonnet 4.6: Pass.** Section 3.6 of the memo is titled 'Inter-matter duplication with the DOE Matter (§6.6)' and explicitly cites §6.6 as the governing provision for the cross-matter research issue. The summary table in Section 7 also references '§6.6' for the DOE-invoice disallowance. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The memo explicitly identifies inter-matter duplication with the DOE matter and cites Guidelines §6.6 as the governing provision, including in the standards table, Section 3.6 heading and analysis, and recommended DOE-invoice disallowance.

### C-030

Issue 11: Identifies arithmetic error in research efficiency discount ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L250))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the discount arithmetic error in Section 6 (Invoice Integrity Issues): 'Discount arithmetic. $7,732.00 is presented as 15% of $54,104.50, which is actually $8,115.68.' This matches the criterion's requirement to identify that the claimed 15% discount of $7,732.00 is understated, and that 15% of $54,104.50 is actually $8,115.68. The error is also referenced in the Executive Summary: 'the "15%" research discount of $7,732.00 is really only 14.29%; 15% would be $8,115.68.'
- **GPT-5.5: Pass.** The memo explicitly identifies the research discount arithmetic error: it states that the claimed 15% discount of $7,732.00 on $54,104.50 is actually only 14.29%, and that 15% should be $8,115.68. This satisfies the criterion even though it does not separately state the $383.68 difference.

### C-031

Issue 11: Calculates correct discount amount (~$8,115.68) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L258))

- **Sonnet 4.6: Pass.** The memo explicitly states in Section 6 (Invoice Integrity Issues): 'Discount arithmetic. $7,732.00 is presented as 15% of $54,104.50, which is actually $8,115.68.' This directly identifies the correct 15% discount amount as $8,115.68, satisfying the criterion.
- **GPT-5.5: Pass.** The memo explicitly states that the claimed $7,732.00 “15%” research discount is incorrect and that 15% would be $8,115.68, satisfying the criterion.

### C-032

Issue 12: Identifies duplicative unjust enrichment research (July 23-24) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L266))

- **Sonnet 4.6: Pass.** The memo in Section 3.2 identifies duplicative unjust enrichment research under the entry 'Unjust enrichment elements and defenses (§6.4 treats elements + defenses as the same issue)' with Osei L70 allowed and Takahashi L73 disallowed. The criterion requires identification of Osei (4.0 hrs, July 23) and Takahashi (3.5 hrs, July 24) researching unjust enrichment on consecutive days. The memo does flag this duplication and disallows Takahashi's entry, though it references line numbers (L70, L73) rather than explicit dates and hours. The criterion is satisfied because the unjust enrichment research duplication is flagged and addressed under §6.4.
- **GPT-5.5: Pass.** The memo flags “Unjust enrichment elements and defenses” as duplicative research under §6.4, allowing Osei L70 and disallowing Takahashi L73. Although it does not expressly state the July 23–24 dates or 7.5-hour total in that table, it identifies the Osei/Takahashi overlap on unjust enrichment research and treats it as a duplicative research violation.

### C-033

Issue 13: Flags July MTCA research as potentially duplicative of June work ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L274))

- **Sonnet 4.6: Fail.** The memo does mention that July topics repeat research billed in June, specifically noting 'spoliation (Takahashi, 6/25), unjust enrichment (Osei, 6/20), and MTCA contractor liability (Wendt/Takahashi, 6/3--6/11)' in Section 3.2. However, the criterion requires the memo to specifically note that the June invoice included approximately 14.5 hours of MTCA research (8.0 hrs Wendt + 6.5 hrs Takahashi) to support the summary judgment motion filed June 14, and to question whether the approximately 16.7 additional hours of MTCA research in July is genuinely incremental or largely redundant. The memo only briefly mentions the June MTCA research in passing without providing the specific hour counts (14.5 hrs in June, 16.7 hrs in July) or explicitly questioning whether the July work is incremental versus redundant with June's work. The criterion requires a more detailed cross-month analysis with specific hour figures and an explicit question about redundancy, which the memo does not provide.
- **GPT-5.5: Fail.** The memo does mention that July MTCA contractor-liability research repeats June work by Wendt/Takahashi and identifies June dates, so it raises a cross-month concern in general. However, it does not note the required specifics: approximately 14.5 hours of June MTCA research, the Wendt/Takahashi split, the June 14 summary judgment motion context, or the approximately 16.7 July hours and whether they were genuinely incremental. Therefore it does not satisfy the criterion as stated.

### C-034

Issue 13: Acknowledges reply brief may justify some additional research ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L282))

- **Sonnet 4.6: Pass.** The memo mentions the reply brief in multiple places. In section 3.1 (line 41), it notes that Briggs billed Rule 56/CERCLA SJ standards research for the reply brief but that 'the research came after the filing' (filed 7/11 per L36, and again 7/19 per L63), and disallows it. In section 3.2, it allows Takahashi L1 and L6 for MTCA/SJ research for the reply brief as the 'most junior qualified researcher.' The memo also notes in section 3.2 that prior-month research on the same topics supports the reductions. However, the criterion requires the memo to acknowledge that some additional MTCA research in July 'may be justified by the reply brief filed July 19, 2024, while still questioning the volume as potentially excessive.' The memo does allow some MTCA research (Takahashi L1, L6) as justified by the reply brief, and it does question the volume by disallowing duplicative entries. It also raises the prior-month duplication concern. The memo thus satisfies both prongs of the criterion: it acknowledges the reply brief context justifies some research while questioning the volume/duplication, and it raises prior-month duplication concerns.
- **GPT-5.5: Pass.** The memo does address the reply-brief context for MTCA research: it identifies MTCA contractor liability / summary judgment research as tied to the reply brief and allows Takahashi’s July MTCA entries as the primary research driven by the Cascade reply brief. It also questions the volume by disallowing overlapping higher-rate entries and expressly notes that MTCA contractor-liability research repeated work billed in June. Although the memo is somewhat inconsistent about the reply filing date, it satisfies the criterion.

### C-035

Distractor 5: Does not flag litigation database hosting as improper ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L290))

- **Sonnet 4.6: Pass.** The memo does not mention the Evergreen Litigation Support database hosting charge at all. It only flags the Westlaw charge (D-1, $4,850) as a violation of §9.3. Since the memo neither recommends reducing nor disallowing a $3,325 Evergreen Litigation Support database hosting charge, the criterion is satisfied.
- **GPT-5.5: Pass.** The memo disallows Westlaw charges under Section 9.3 and withholds certain expert/travel/copying disbursements, but it does not mention or recommend reducing/disallowing the $3,325 Evergreen Litigation Support database hosting charge as a billing guideline violation.

### C-036

Memo states correct invoice total amount ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L298))

- **Sonnet 4.6: Pass.** The memo states in the adjustment table: 'Invoice total as billed: $387,420.50', which matches the required invoice total. The criterion is satisfied.
- **GPT-5.5: Pass.** The memo explicitly states 'Invoice total as billed $387,420.50' in the executive summary table, which matches the required invoice total.

### C-037

Memo includes a summary table of all recommended adjustments ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L306))

- **Sonnet 4.6: Pass.** Section 7 of the memo contains a clearly formatted summary table titled 'Summary of Recommended Adjustments' that consolidates all recommended adjustments with dollar amounts, including research fee adjustments, non-research fee adjustments, Westlaw disbursement, withheld amounts, and DOE-invoice disallowances. The table provides individual line items and subtotals, satisfying the criterion.
- **GPT-5.5: Pass.** The memo includes a consolidated “Summary of Recommended Adjustments” table with categories, dollar amounts, a subtotal for research fee adjustments, total disallowed/reduced amount, withheld amounts, and related recommended invoice credits/disallowances.

### C-038

Memo includes severity assessments for identified issues ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L314))

- **Sonnet 4.6: Fail.** The memo does not assign any severity ratings (such as Critical, Significant, Minor, or equivalent priority rankings) to the identified issues. While the memo is detailed and organizes issues into categories with dollar amounts, it never labels any issue as 'critical,' 'high priority,' 'significant,' 'minor,' or uses any equivalent severity/priority ranking system. The issues are presented in a structured format but without explicit severity assessments.
- **GPT-5.5: Fail.** The memo identifies and quantifies many issues, but it does not assign severity ratings or an equivalent priority ranking such as Critical/Significant/Minor to the major issues. Listing issues, recommendations, and dollar adjustments is not the same as severity assessment.

### C-039

Issue 2: Cites Section 6.3 for partner research restriction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L322))

- **Sonnet 4.6: Pass.** The memo explicitly cites Section 6.3 multiple times in connection with partner research billing. In Section 3.1, the heading reads 'Partner research (§6.3)' and the table entries reference '§§6.3, 6.4' as the provisions violated. The Summary of Recommended Adjustments also references '§6.3/§6.4' for partner research disallowances. Section 6.3 is clearly and repeatedly cited as the provision violated by partner research billing.
- **GPT-5.5: Pass.** The memo explicitly identifies “Partner research (§6.3)” and states that Guidelines §6.3 prohibits partners from billing research at full partner rates absent required notation, citing §6.3 for the partner research reductions/disallowances.

### C-040

Issue 3: Cites Section 6.4 for duplicative MTCA research ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L330))

- **Sonnet 4.6: Pass.** The memo explicitly cites Section 6.4 in connection with duplicative MTCA research. In Section 3.1, partner entries for MTCA preemption/contractor defense (Hargrove L24) are disallowed under '§§6.3, 6.4'. In Section 3.2, the table shows 'MTCA contractor liability / SJ standards (reply brief)' with disallowed entries citing §6.4 as the governing provision. The memo also references §6.6 for the inter-matter MTCA duplication between Cascade and DOE invoices, but §6.4 is clearly and explicitly cited for the duplicative MTCA research across timekeepers within the same matter.
- **GPT-5.5: Pass.** The memo explicitly addresses duplicative MTCA contractor-liability research across timekeepers in Section 3.2 under “Duplicative research by multiple timekeepers (§6.4)” and cites §6.4. It also cites §6.4 for overlapping MTCA partner research in Section 3.1.

### C-041

Issue 7: Cites Section 4.3 for onboarding/get-up-to-speed entries ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L338))

- **Sonnet 4.6: Pass.** In Section 3.3, the memo cites '§§4.3, 6.4' as the governing provisions for the background/familiarization research entries (Lines 42, 60, 78), which include 'familiarize with MTCA amendments' and 'get up to speed on technical remediation issues.' Section 4.3 is explicitly cited in connection with these onboarding/get-up-to-speed entries.
- **GPT-5.5: Pass.** The memo explicitly cites §§4.3 and 6.4 in Section 3.3, titled “Background / familiarization research,” for entries described as “familiarize” and “get up to speed.” It also describes §4.3 as governing onboarding/catch-up research in the standards section.

### C-042

Issue 9: Cites Section 9.3 for Westlaw disbursement violation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L346))

- **Sonnet 4.6: Pass.** The memo explicitly cites Section 9.3 multiple times in connection with the Westlaw disbursement charge. In Section 4 ('Research-Related Disbursement: Westlaw (§9.3)'), the heading itself references §9.3, and the text states 'Section 9.3 and Engagement Letter §5 prohibit this charge outright.' Additionally, in the governing standards table, §9.3 is listed as prohibiting Westlaw/Lexis charges. The summary table also lists 'Westlaw disbursement (§9.3)' as a line item.
- **GPT-5.5: Pass.** The memo explicitly identifies the Westlaw disbursement charge and cites Guidelines Section 9.3 as prohibiting Westlaw/Lexis pass-through charges, including in the governing standards, executive summary, Section 4, and adjustment tables.

### C-043

Summary table total reflects aggregation of individual adjustments ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L354))

- **Sonnet 4.6: Pass.** Let me check the summary table arithmetic in Section 7. The summary table lists: - Partner research: ($7,981.00) - Duplicative associate research: ($12,962.50) - Background/familiarization research: ($4,152.50) - Senior Associate routine research: ($1,127.50) - Research fee adjustments subtotal: ($26,223.50) Check: 7,981.00 + 12,962.50 + 4,152.50 + 1,127.50 = 26,223.50 ✓ - Non-research fee adjustments: ($6,310.00) - Westlaw disbursement: ($4,850.00) - Total disallowed/reduced: ($37,383.50) Check: 26,223.50 + 6,310.00 + 4,850.00 = 37,383.50 ✓ Now let me verify the individual components: Partner research ($7,981.00): - L7 disallowed: $1,812.50 - L24 disallowed: $1,611.00 - L41 disallowed: $2,175.00 - L74 disallowed: $1,087.50 - L51 reduced: $770.00 - L92 reduced: $525.00 Total: 1,812.50 + 1,611.00 + 2,175.00 + 1,087.50 + 770.00 + 525.00 = 7,981.00 ✓ Duplicative associate research ($12,962.50): - MTCA: $3,060.00 - Spoliation: $1,190.00 - ESI proportionality: $1,360.00 - Consequential damages: $1,190.00 - Economic loss rule: $2,040.00 - Privilege log: $1,020.00 - Lost profits: $1,912.50 - Unjust enrichment: $1,190.00 Total: 3,060 + 1,190 + 1,360 + 1,190 + 2,040 + 1,020 + 1,912.50 + 1,190 = 12,962.50 ✓ Background research ($4,152.50): - L42: $1,062.50 - L60: $1,475.00 - L78: $1,615.00 Total: 1,062.50 + 1,475.00 + 1,615.00 = 4,152.50 ✓ Senior Associate routine research ($1,127.50): - L19: $717.50 - L64: $410.00 Total: 717.50 + 410.00 = 1,127.50 ✓ Non-research fee adjustments ($6,310.00): - L158: $1,090.00 - L159: $1,450.00 - L160: $725.00 - L142: $885.00 - L155: $725.00 - L31: $615.00 - L79: $820.00 Total: 1,090 + 1,450 + 725 + 885 + 725 + 615 + 820 = 6,310.00 ✓ All arithmetic checks out correctly.
- **GPT-5.5: Pass.** The summary adjustment table’s components add correctly: $7,981.00 + $12,962.50 + $4,152.50 + $1,127.50 = $26,223.50 for research adjustments, and $26,223.50 + $6,310.00 + $4,850.00 = $37,383.50 total disallowed/reduced. The executive payment table also reconciles arithmetically to the stated $222,732.10 payable amount.

### C-044

Issue 4: Recommends dollar adjustment for damages research duplication ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L362))

- **Sonnet 4.6: Pass.** The memo in Section 3.2 explicitly recommends dollar adjustments for duplicative research on consequential damages and lost profits. Specifically, it disallows Takahashi L11 (consequential damages, WA) with a reduction of ($1,190.00) while allowing Osei L20, and disallows Wendt L55 (lost profits damages, WA) with a reduction of ($1,912.50) while allowing Takahashi L56. Both adjustments are included in the subtotal of ($12,962.50) for duplicative associate research.
- **GPT-5.5: Pass.** The memo identifies duplicative damages-related research and recommends specific dollar reductions: consequential damages research disallowing Takahashi L11 for $1,190, and lost profits damages research disallowing Wendt L55 for $1,912.50. This satisfies the requirement to recommend a dollar adjustment for at least some duplicative consequential damages/lost profits research.

### C-045

Issue 6: Recommends dollar adjustment for spoliation/ESI duplication ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L370))

- **Sonnet 4.6: Pass.** The memo in Section 3.2 explicitly addresses the spoliation/ESI sanctions research duplication. It identifies Takahashi L86 as the allowed entry and disallows Wendt L87 ($1,190.00) as duplicative under §6.4. Additionally, Briggs L7 and L74 are disallowed under §§6.3 and 6.4 in Section 3.1 ($1,812.50 and $1,087.50 respectively). The memo recommends specific dollar adjustments for these duplicative entries, satisfying the criterion.
- **GPT-5.5: Pass.** The memo specifically identifies duplicative spoliation/ESI sanctions research, allows Takahashi L86, disallows Wendt L87 with a $1,190 reduction, and also disallows overlapping Briggs entries. This recommends a dollar adjustment for the duplication, including the Takahashi/Wendt overlap.

### C-046

Osei's July 19 background research flagged as potentially non-billable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L378))

- **Sonnet 4.6: Pass.** In Section 3.3 of the memo, the agent explicitly flags Osei L60 (5.0 hours, $1,475.00) with the description 'Background research on environmental remediation industry standards... to understand technical aspects of case' as non-billable background/familiarization research under §§4.3, 6.4, recommending a reduction of ($1,475.00). The criterion asks about Osei's July 19 entry (5.0 hrs, $1,475) with that exact description. The line number differs (L60 vs the criterion's reference to July 19), but the timekeeper, hours, amount, and description all match. The entry is clearly flagged as problematic and disallowed.
- **GPT-5.5: Pass.** The memo specifically flags Osei’s 5.0-hour, $1,475 entry for “Background research on environmental remediation industry standards... to understand technical aspects of case” in Section 3.3 as background/familiarization research and recommends disallowing it under §§4.3 and 6.4.

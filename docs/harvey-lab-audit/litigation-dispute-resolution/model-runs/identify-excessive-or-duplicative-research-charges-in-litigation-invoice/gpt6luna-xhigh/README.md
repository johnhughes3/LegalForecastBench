# GPT-6 Luna (xhigh): Identify Excessive or Duplicative Research Charges in Litigation Invoice

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json) · [Claude Opus 5.5 (low) run](../opus55-low/README.md) · [All runs](../../README.md)

**Model:** `gpt-6-luna`, reasoning effort `xhigh`. **Run:** `20260926-201603`.

**Native grades:** Sonnet 4.6 passed 34 of 46 criteria; GPT-5.5 passed 36 of 46 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

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
| [C-006](#c-006) | Issue 1: Calculates 12% cap dollar amount as approximately $41,018 | Pass | Pass |
| [C-007](#c-007) | Issue 2: Identifies Diane Hargrove's partner research billing violation | Pass | Pass |
| [C-008](#c-008) | Issue 2: Identifies specific Hargrove research entries (July 9, 17, 30) | **Fail** | **Fail** |
| [C-009](#c-009) | Issue 2: Calculates Hargrove overcharge as approximately $1,925 | **Fail** | **Fail** |
| [C-010](#c-010) | Issue 2: Notes Hargrove's entries lack required exceptional circumstances notation | Pass | Pass |
| [C-011](#c-011) | Issue 2: Identifies Nathan Briggs's partner research billing violation | Pass | Pass |
| [C-012](#c-012) | Issue 2: Calculates Briggs overcharge as approximately $1,260 | **Fail** | Pass |
| [C-013](#c-013) | Issue 3: Identifies duplicative MTCA research across Takahashi and Wendt | Pass | Pass |
| [C-014](#c-014) | Issue 3: References specific duplicative MTCA entries | Pass | Pass |
| [C-015](#c-015) | Issue 3: Calculates recommended adjustment for duplicative MTCA research | Pass | Pass |
| [C-016](#c-016) | Issue 4: Identifies duplicative consequential/lost profits damages research | **Fail** | **Fail** |
| [C-017](#c-017) | Issue 4: Notes Osei's excessive hours (13.0 hrs) on one research topic | **Fail** | **Fail** |
| [C-018](#c-018) | Issue 5: Identifies duplicative economic loss rule research on July 12 | Pass | Pass |
| [C-019](#c-019) | Issue 5: Recommends adjustment for economic loss rule duplication | Pass | Pass |
| [C-020](#c-020) | Issue 6: Identifies duplicative spoliation/ESI sanctions research | Pass | Pass |
| [C-021](#c-021) | Issue 7: Flags Wendt's July 25 'get up to speed' entry as non-billable | Pass | Pass |
| [C-022](#c-022) | Issue 7: Flags Wendt's July 15 'familiarize' entry as non-billable | Pass | **Fail** |
| [C-023](#c-023) | Issue 7: Calculates total onboarding adjustment (~$2,677.50) | **Fail** | Pass |
| [C-024](#c-024) | Issue 8: Flags block-billed 'research and draft' entries under Section 6.5 | Pass | Pass |
| [C-025](#c-025) | Issue 8: Notes Section 6.5 requires 50% allocation to non-research | **Fail** | **Fail** |
| [C-026](#c-026) | Issue 9: Identifies Westlaw disbursement charge as prohibited | Pass | Pass |
| [C-027](#c-027) | Issue 9: Recommends $4,850 adjustment for Westlaw disbursement | Pass | Pass |
| [C-028](#c-028) | Issue 10: Identifies inter-matter duplicative MTCA research with DOE Matter | Pass | Pass |
| [C-029](#c-029) | Issue 10: Cites Section 6.6 for inter-matter research prohibition | Pass | Pass |
| [C-030](#c-030) | Issue 11: Identifies arithmetic error in research efficiency discount | Pass | Pass |
| [C-031](#c-031) | Issue 11: Calculates correct discount amount (~$8,115.68) | Pass | Pass |
| [C-032](#c-032) | Issue 12: Identifies duplicative unjust enrichment research (July 23-24) | Pass | Pass |
| [C-033](#c-033) | Issue 13: Flags July MTCA research as potentially duplicative of June work | **Fail** | Pass |
| [C-034](#c-034) | Issue 13: Acknowledges reply brief may justify some additional research | Pass | Pass |
| [C-035](#c-035) | Distractor 5: Does not flag litigation database hosting as improper | Pass | Pass |
| [C-036](#c-036) | Memo states correct invoice total amount | Pass | Pass |
| [C-037](#c-037) | Memo includes a summary table of all recommended adjustments | **Fail** | **Fail** |
| [C-038](#c-038) | Memo includes severity assessments for identified issues | **Fail** | **Fail** |
| [C-039](#c-039) | Issue 2: Cites Section 6.3 for partner research restriction | Pass | Pass |
| [C-040](#c-040) | Issue 3: Cites Section 6.4 for duplicative MTCA research | Pass | Pass |
| [C-041](#c-041) | Issue 7: Cites Section 4.3 for onboarding/get-up-to-speed entries | Pass | Pass |
| [C-042](#c-042) | Issue 9: Cites Section 9.3 for Westlaw disbursement violation | Pass | Pass |
| [C-043](#c-043) | Summary table total reflects aggregation of individual adjustments | **Fail** | **Fail** |
| [C-044](#c-044) | Issue 4: Recommends dollar adjustment for damages research duplication | Pass | Pass |
| [C-045](#c-045) | Issue 6: Recommends dollar adjustment for spoliation/ESI duplication | Pass | Pass |
| [C-046](#c-046) | Osei's July 19 background research flagged as potentially non-billable | Pass | Pass |

## Judge reasoning

### C-001

Issue 1: Identifies research charges exceed 12% cap (Section 6.2) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L18))

- **Sonnet 4.6: Pass.** The memo explicitly identifies that research charges exceed the 12% cap in Section 2, citing Section 6.2. It provides a table showing the net research amounts, the 12% ceiling, and the excess for both Cascade and DOE matters. The memo states 'Section 6.2 caps research at 12% absent prior written approval' and calculates the specific overages (\ $5,354.04 for Cascade on Summary-tab figures and \ $24.30 for DOE).
- **GPT-5.5: Pass.** The memo expressly cites Section 6.2 as imposing a 12% cap on research absent prior written approval and identifies that Cascade’s reported research ratio is 13.56%, exceeding the cap, with calculated overage amounts. It also notes a DOE cap overage.

### C-002

Issue 1: Calculates net research percentage as approximately 13.56% ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L26))

- **Sonnet 4.6: Pass.** The memo explicitly states 'Cascade's reported research ratio is 13.56% (the Summary tab rounds to 13.56%), already over the cap.' This matches the criterion requiring the memo to calculate or state that net research charges ($46,372.50) as a percentage of total fees ($341,820.50) is approximately 13.56%.
- **GPT-5.5: Pass.** The memo explicitly states that Cascade's reported research ratio is 13.56%, using net research charges of $46,372.50 and total/net professional fees of $341,820.50, which matches the required approximate percentage.

### C-003

Issue 1: Calculates gross research percentage as approximately 15.83% ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L34))

- **Sonnet 4.6: Fail.** The memo states that 'Cascade's reported research ratio is 13.56%' and discusses the 12% cap, but it does not calculate or state the gross research percentage of approximately 15.83% (i.e., $54,104.50 / $341,820.50). The 13.56% figure appears to be the net research ratio after the discount ($46,372.50 / $341,820.50 ≈ 13.56%). The gross percentage of ~15.83% is never mentioned in the memo.
- **GPT-5.5: Fail.** The memo identifies gross research charges of $54,104.50 and total fees of $341,820.50, but it does not calculate or state the gross research percentage of approximately 15.83%. It instead states a net research ratio of 13.56%.

### C-004

Issue 1: Notes no prior written approval from Marcus Holt for cap exceedance ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L42))

- **Sonnet 4.6: Pass.** The memo explicitly states in Section 2: 'The June 28 email specifically reminded H&L that Section 6.2 caps research at 12% absent prior written approval, identified prior MTCA duplication, and cautioned that July MTCA research should build on work already completed. The email did not approve an exception; it expressly required advance written approval. None is in the materials reviewed.' This directly addresses the lack of prior written approval from Marcus Holt (the June 28 email was from Marcus Holt to H&L) for exceeding the 12% research cap under Section 6.2.
- **GPT-5.5: Pass.** The memo explicitly states that Section 6.2 caps research at 12% absent prior written approval, that Marcus Holt's June 28 email did not approve an exception and required advance written approval, and that no such approval was in the materials reviewed.

### C-005

Issue 1: References Holt's June 28 email as notice to firm about cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L50))

- **Sonnet 4.6: Pass.** The memo explicitly references Marcus Holt's June 28, 2024 email to H&L in multiple places. In Section 2, it states: 'The June 28 email specifically reminded H&L that Section 6.2 caps research at 12% absent prior written approval, identified prior MTCA duplication, and cautioned that July MTCA research should build on work already completed. The email did not approve an exception; it expressly required advance written approval.' The email is also listed in the Materials Reviewed section and referenced again in Section 2.3 and Section 2.4. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly references Marcus Holt's June 28, 2024 email, stating that it reminded H&L that Section 6.2 caps research at 12% absent prior written approval and required advance written approval/compliance for July research.

### C-006

Issue 1: Calculates 12% cap dollar amount as approximately $41,018 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L58))

- **Sonnet 4.6: Pass.** The memo explicitly states in the research cap table: 'Cascade --- Summary-tab figures: Net research $46,372.50, Net professional fees used $341,820.50, 12% ceiling $41,018.46, Excess as submitted $5,354.04.' This directly calculates 12% of $341,820.50 as $41,018.46, which matches the criterion's requirement of approximately $41,018.
- **GPT-5.5: Pass.** The memo explicitly provides a table showing for Cascade, using Summary-tab figures, net professional fees of $341,820.50, a 12% ceiling of $41,018.46, and excess of $5,354.04. This satisfies the requirement to calculate the cap amount as approximately $41,018.

### C-007

Issue 2: Identifies Diane Hargrove's partner research billing violation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L66))

- **Sonnet 4.6: Pass.** The memo in Section 2.1 explicitly identifies Diane Hargrove's partner research billing: 'Diane Hargrove, 5.5 hours/$4,922.50' as one of the six partner-coded RES entries violating Section 6.3. The memo flags this as a billing violation and recommends reducing the rate to the senior-associate rate of $545/hour. However, the criterion specifies that Hargrove's rate should be $895/hr, while the memo shows $4,922.50 / 5.5 hours = $895/hour, which matches. The memo does identify Hargrove's partner research billing violation under Section 6.3, satisfying the criterion.
- **GPT-5.5: Pass.** The memo explicitly flags Section 6.3's bar on partner research at partner rates and identifies Diane Hargrove's research as 5.5 hours billed at $4,922.50, which corresponds to her $895/hr partner rate, recommending reduction or disallowance.

### C-008

Issue 2: Identifies specific Hargrove research entries (July 9, 17, 30) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L74))

- **Sonnet 4.6: Fail.** The memo mentions 'July 9 Hargrove MTCA-preemption/contractor-defense research' in section 2.4, but this is the only specific Hargrove entry identified. The July 17 and July 30 Hargrove entries are not specifically identified anywhere in the memo. The criterion requires at least two of the three specific Hargrove entries (July 9, July 17, July 30) to be identified. Only one is mentioned, so the criterion is not met.
- **GPT-5.5: Fail.** The memo specifically mentions Hargrove's July 9 research entry, but it does not specifically identify Hargrove's July 17 or July 30 research entries. Identifying the combined Hargrove partner research total is not enough to identify at least two of the three required dated entries.

### C-009

Issue 2: Calculates Hargrove overcharge as approximately $1,925 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L82))

- **Sonnet 4.6: Fail.** The memo in Section 2.1 addresses partner research entries including Diane Hargrove (5.5 hours/$4,922.50) and Nathan Briggs (7.0 hours/$5,075.00). It recommends reducing the combined $9,997.50 to $6,812.50 at $545/hour, a $3,185.00 combined reduction. However, it does not separately calculate the Hargrove-specific overcharge of approximately $1,925.00 (5.5 hrs × ($895 - $545) = $1,925.00). The memo combines both partner entries into a single aggregate reduction without isolating Hargrove's individual adjustment. The criterion requires either a ~$1,925 calculation for Hargrove specifically or a recommendation to write off the full $4,922.50. Neither is present in the memo.
- **GPT-5.5: Fail.** The memo identifies Hargrove’s 5.5 hours/$4,922.50 and says partner research should be reduced to $545/hour, but it only provides a combined Hargrove/Briggs reduction of $3,185 and does not calculate Hargrove’s specific $1,925 overcharge or recommend writing off Hargrove’s full $4,922.50.

### C-010

Issue 2: Notes Hargrove's entries lack required exceptional circumstances notation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L90))

- **Sonnet 4.6: Pass.** Section 2.1 of the memo explicitly states that the six partner-coded RES entries 'contain no such notation' referring to the required explanation of why delegation was not possible and why partner involvement was necessary. Diane Hargrove is specifically named as one of the partners with entries lacking this notation (5.5 hours/$4,922.50). This directly addresses the criterion that the memo notes Hargrove's research entries lack the required exceptional circumstances notation as required by Section 6.3.
- **GPT-5.5: Pass.** The memo explicitly states that Section 6.3 requires an explanation for partner research and that the partner-coded RES entries, including Diane Hargrove’s 5.5 hours, “contain no such notation.”

### C-011

Issue 2: Identifies Nathan Briggs's partner research billing violation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L98))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Nathan Briggs as a partner with 7.0 hours billed at $5,075.00 (which is 7.0 × $725/hr) for research entries, flagging this as a violation of Section 6.3 which bars partner research at partner rates. This appears in Section 2.1 of the memo.
- **GPT-5.5: Pass.** The memo expressly flags Nathan Briggs under “Partner and senior-associate research,” stating that he billed 7.0 hours/$5,075.00 in partner-coded research entries and that Section 6.3 bars partner research at partner rates, recommending a rate reduction or disallowance.

### C-012

Issue 2: Calculates Briggs overcharge as approximately $1,260 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L106))

- **Sonnet 4.6: Fail.** The memo addresses Briggs's research entries in Section 2.1, noting that Nathan Briggs billed 7.0 hours at $5,075.00 and recommends reducing to $545/hour (senior-associate rate), yielding a combined reduction of $3,185.00 for both Hargrove and Briggs together. However, the memo does not separately calculate the Briggs-specific overcharge of approximately $1,260 (7.0 hrs × ($725 - $545) = $1,260). The criterion requires either a ~$1,260 calculation for Briggs specifically or a recommendation to write off the full $5,075. The memo provides only a combined reduction figure for both partners and does not isolate Briggs's individual overcharge amount. Additionally, in Section 2.2, Briggs's spoliation/ESI entries are recommended for full disallowance as duplicative, but this is not the same as calculating the rate-reduction overcharge. The criterion is not satisfied.
- **GPT-5.5: Pass.** The memo identifies Briggs’s 7.0 hours billed at $5,075 and recommends re-rating the partner research entries to the $545 senior associate rate, calculating a combined partner-research reduction of $3,185. Although it does not separately state “Briggs overcharge = $1,260,” the calculation necessarily includes Briggs’s 7.0 × ($725-$545) = $1,260 adjustment.

### C-013

Issue 3: Identifies duplicative MTCA research across Takahashi and Wendt ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L114))

- **Sonnet 4.6: Pass.** The memo explicitly identifies in Section 2.2 that Wendt (July 1, 3.2h and July 5, 4.0h) and Takahashi both researched the MTCA contractor-liability framework during July 1-2, citing Section 6.4 as the basis for the duplicative research prohibition. The memo recommends a $3,060.00 credit for this overlap and instructs to retain the most junior qualified researcher's work. This directly satisfies the criterion of identifying overlapping MTCA liability/contractor liability research billed by both Takahashi and Wendt.
- **GPT-5.5: Pass.** The memo explicitly identifies overlapping MTCA contractor-liability research by Wendt on July 1 and July 5 and Takahashi on July 1–2, references summary-judgment-related overlap, and invokes Section 6.4’s duplicative research rule to recommend retaining only the junior qualified researcher’s work.

### C-014

Issue 3: References specific duplicative MTCA entries ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L122))

- **Sonnet 4.6: Pass.** The memo in Section 2.2 explicitly identifies 'MTCA contractor liability: Wendt July 1, 3.2h/$1,360; Wendt July 5, 4.0h/$1,700. Takahashi also researched the MTCA contractor-liability framework July 1--2.' as duplicative entries. This references both Wendt's July 1 (3.2 hrs) and July 5 (4.0 hrs) entries, and Takahashi's July 1-2 research, satisfying the criterion that at least Takahashi's July 1 entry and Wendt's July 1 or July 5 entries be identified as duplicative.
- **GPT-5.5: Pass.** The memo identifies the MTCA contractor-liability research as duplicative, specifically listing Wendt’s July 1 (3.2h) and July 5 (4.0h) entries and stating that Takahashi also researched the same MTCA contractor-liability framework on July 1–2. Although it does not state Takahashi’s 4.5 hours, it does reference the relevant Takahashi July 1 research in the duplicative pairing with Wendt’s entries.

### C-015

Issue 3: Calculates recommended adjustment for duplicative MTCA research ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L130))

- **Sonnet 4.6: Pass.** The memo explicitly recommends a $3,060.00 credit for the MTCA contractor liability duplication involving Wendt's July 1 (3.2h/$1,360) and July 5 (4.0h/$1,700) entries, which total $3,060.00. This matches the criterion's calculation of at least 7.2 hrs at $425/hr = $3,060. The adjustment is clearly stated in Section 2.2.
- **GPT-5.5: Pass.** The memo expressly identifies duplicative MTCA contractor-liability research by Wendt overlapping with Takahashi and recommends a $3,060 gross credit, which matches 7.2 hours at $425/hour and satisfies the criterion.

### C-016

Issue 4: Identifies duplicative consequential/lost profits damages research ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L138))

- **Sonnet 4.6: Fail.** The criterion requires the memo to identify duplicative consequential damages and lost profits research, specifically noting that lost profits is a subset of consequential damages (i.e., that these two research topics overlap). The memo does identify both: (1) Consequential damages duplication: Takahashi July 3 (3.5h) and Osei July 8-10 (13.0h) - though the hours don't exactly match the criterion's specific entries of July 8 (7.5 hrs) and July 10 (5.5 hrs), the memo does reference Osei's July 8-10 research on consequential damages. (2) Lost profits duplication: Wendt July 18 (4.5h) and Takahashi July 18 (3.5h) - these match exactly. However, the criterion specifically requires noting that 'lost profits is a subset of consequential damages' - i.e., that these two research clusters are themselves duplicative of each other. The memo treats them as separate duplication clusters rather than identifying that lost profits research duplicates consequential damages research. The memo lists them as two separate line items without connecting them as overlapping topics. The criterion says PASS if the memo identifies that consequential damages and lost profits research was duplicated 'noting that lost profits is a subset of consequential damages.' The memo does not make this connection - it treats them as independent duplication issues rather than noting the substantive overlap between the two topics across timekeepers. This is a FAIL on the specific requirement to note that lost profits is a subset of consequential damages.
- **GPT-5.5: Fail.** The memo flags consequential damages research by Osei on July 8–10 and lost profits research by Wendt/Takahashi on July 18 as duplicative across timekeepers. However, it treats them as separate duplicate categories and does not note that lost profits is a subset of consequential damages, which the criterion specifically requires.

### C-017

Issue 4: Notes Osei's excessive hours (13.0 hrs) on one research topic ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L146))

- **Sonnet 4.6: Fail.** The criterion requires the memo to flag that Amara Osei spent approximately 13 hours total (7.5 hrs on July 8 + 5.5 hrs on July 10) on Washington consequential damages law as excessive. Looking at the memo, Section 2.2 mentions 'Osei July 8--10, 13.0h/\$3,835.00' in the context of the consequential damages duplication entry, but this is flagged as duplicative with Takahashi's work on the same topic, not as independently excessive hours on a single research question. The memo does not separately flag Osei's 13 hours as excessive in themselves — it only notes the overlap with Takahashi. Furthermore, the criterion specifies the breakdown as 7.5 hrs on July 8 + 5.5 hrs on July 10, but the memo groups them as 'July 8--10, 13.0h' without breaking them down that way or characterizing the total as excessive for a single research question. The memo's treatment is about duplication, not about the excessiveness of Osei's hours on this single topic. The criterion asks specifically for flagging excessive hours on one research question, which the memo does not do.
- **GPT-5.5: Fail.** The memo mentions Osei’s 13.0 hours on consequential damages/foreseeability, but only in the context of overlap with Takahashi and recommends retaining Osei’s work. It does not flag Osei’s 7.5 + 5.5 hours on a single consequential-damages research question as excessive.

### C-018

Issue 5: Identifies duplicative economic loss rule research on July 12 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L154))

- **Sonnet 4.6: Pass.** The memo explicitly identifies in Section 2.2 that Takahashi researched the Washington economic-loss rule on July 12 for 6.0h/$2,040 and Osei researched the same topic on July 12 for 4.5h/$1,327.50, noting it was the 'same doctrine and same day' and recommending a $2,040.00 credit under Section 6.4.
- **GPT-5.5: Pass.** The memo explicitly identifies the July 12 Washington economic-loss rule duplication: Takahashi billed 6.0 hours/$2,040 and Osei billed 4.5 hours/$1,327.50 on the same doctrine and same day, citing Section 6.4 and recommending a credit. This satisfies the criterion.

### C-019

Issue 5: Recommends adjustment for economic loss rule duplication ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L162))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the Washington economic-loss rule duplication in Section 2.2. It identifies Takahashi July 12 (6.0h/$2,040) and Osei July 12 (4.5h/$1,327.50) as duplicative research on the same doctrine on the same day, and recommends a credit of $2,040.00 (disallowing Takahashi's higher-rate work and retaining Osei's lower-rate work). This is a dollar adjustment for the economic loss rule duplication. The criterion requires at minimum that Osei's $1,327.50 be recommended for disallowance or a comparable amount. The memo recommends disallowing $2,040.00 (Takahashi's entries), which is a comparable or greater amount. The criterion is satisfied.
- **GPT-5.5: Pass.** The memo specifically identifies duplicative Washington economic-loss rule research and recommends a dollar credit of $2,040.00 for the overlap, which is a comparable/greater adjustment than the minimum $1,327.50 referenced in the criterion.

### C-020

Issue 6: Identifies duplicative spoliation/ESI sanctions research ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L170))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the spoliation/ESI sanctions research duplication in Section 2.2, listing Briggs July 2 (2.5h/$1,812.50) and July 24 (1.5h/$1,087.50), Wendt July 29 (2.8h/$1,190), and Takahashi July 29 (4.3h/$1,462) as overlapping on the same federal spoliation/sanctions framework. It recommends a $4,090.00 credit and retains Takahashi's lower-rate work. This satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly identifies spoliation/ESI sanctions research as duplicative, citing Briggs's July 2 and July 24 entries along with Wendt's July 29 2.8-hour entry and Takahashi's July 29 4.3-hour entry, and recommends removing overlapping time.

### C-021

Issue 7: Flags Wendt's July 25 'get up to speed' entry as non-billable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L178))

- **Sonnet 4.6: Pass.** The memo does flag Wendt's July 25 entry (3.8 hours/$1,615.00) in Section 2.4, describing it as 'review file materials, do background research, and get up to speed' and citing §4.3's onboarding prohibition. However, the memo conditions the disallowance on whether H&L confirms Wendt was 'newly/rotationally assigned,' noting that the engagement letter lists Wendt as assigned since January. The criterion requires the entry to be flagged as non-billable under Section 4.3. The memo does flag it and cite §4.3, but hedges the disallowance. The criterion says PASS if the memo 'identifies' the entry as non-billable under Section 4.3 — the memo does identify it as potentially non-billable under §4.3 and recommends disallowance of the 'orientation component' if H&L confirms new/rotational assignment. This is sufficient identification of the entry as non-billable under §4.3, even if conditional. The entry is flagged with the correct guideline section and the correct reasoning about getting up to speed being non-billable.
- **GPT-5.5: Pass.** The memo specifically identifies Wendt’s July 25 entry as 3.8 hours/$1,615 for reviewing materials/background research and “get up to speed,” recommends disallowance absent support, and expressly references §4.3’s onboarding prohibition, stating the orientation component would be nonbillable in full if applicable.

### C-022

Issue 7: Flags Wendt's July 15 'familiarize' entry as non-billable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L186))

- **Sonnet 4.6: Pass.** The memo does flag Wendt's July 15 entry (2.5 hours/$1,062.50) in Section 2.4, describing it as 'background' research to 'familiarize with' MTCA amendments, and recommends disallowing the $4,152.50 (which includes this entry) absent a corrected substantive explanation. It also references §4.3's onboarding prohibition and notes it applies if Wendt was newly/rotationally assigned. However, the criterion requires the memo to flag this entry as non-billable under Section 4.3 specifically noting the 'familiarize' language indicates background/onboarding research. The memo does mention the 'familiarize with' language and does reference §4.3, but conditions the §4.3 application on H&L confirming Wendt was newly/rotationally assigned (since the engagement letter lists him as assigned since January). The entry is flagged as objectionable and subject to disallowance, with the 'familiarize' language specifically quoted and §4.3 cited. This satisfies the criterion sufficiently.
- **GPT-5.5: Fail.** The memo does mention Wendt’s July 15 2.5-hour/$1,062.50 entry and quotes “familiarize with” MTCA amendments as background research, recommending disallowance absent explanation. However, it flags that entry under §6.5 rather than identifying it as non-billable or objectionable under §4.3 for onboarding/background research; its §4.3 discussion is conditional and tied to the July 25 orientation component, not July 15. Thus it does not fully satisfy the specified criterion.

### C-023

Issue 7: Calculates total onboarding adjustment (~$2,677.50) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L194))

- **Sonnet 4.6: Fail.** The memo addresses Wendt's July 15 (2.5h/$1,062.50) and July 25 (3.8h/$1,615.00) entries and recommends disallowing them, citing a combined total of $4,152.50 (which also includes Osei July 19: 5.0h/$1,475.00). However, the criterion specifically requires calculating approximately $2,677.50 (6.3 hrs × $425/hr) for the Wendt entries alone, or a comparable amount. The memo does not calculate $2,677.50 or any comparable figure specifically for these two Wendt entries. Instead, it lumps them together with Osei's entry into a combined $4,152.50 disallowance. The criterion requires a specific dollar adjustment of approximately $2,677.50 for the getting-up-to-speed entries, which is not present in the memo.
- **GPT-5.5: Pass.** The memo identifies Wendt's July 15 entry as 2.5 hours/$1,062.50 and July 25 entry as 3.8 hours/$1,615.00, and recommends disallowance absent explanation. Those amounts total $2,677.50, even though the memo also combines them with another Osei entry for a $4,152.50 total.

### C-024

Issue 8: Flags block-billed 'research and draft' entries under Section 6.5 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L202))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Osei's July 3 (6.0h/$1,770), July 8 (7.5h/$2,212.50), and July 16 (3.5h/$1,032.50) entries as block-billed entries combining research with drafting without time allocation, and cites Section 6.5 as the basis for the issue. This satisfies all requirements of the criterion.
- **GPT-5.5: Pass.** The memo explicitly flags Amara Osei’s July 3, July 8, and July 16 entries as combining research with drafting without allocating time, and states that under §6.5 they should count toward the research cap unless clearly allocated, with possible reductions for block billing.

### C-025

Issue 8: Notes Section 6.5 requires 50% allocation to non-research ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L210))

- **Sonnet 4.6: Fail.** The memo discusses block-billed entries combining research with drafting (e.g., Osei's July 3, July 8, and July 16 entries) and states that the entire entries will be counted toward research for the cap unless a clear allocation is provided, with a potential 30% reduction under §§5.3/6.5. However, the memo does not articulate the specific Section 6.5 requirement that block-billed entries combining research with other tasks must allocate at least 50% of the time to the non-research component, or the entire entry will be reduced to the research cap rate. The memo references §6.5 but only in the context of requiring entries to identify a specific legal question and its purpose, and for block billing reductions (30% reduction), not the 50% allocation requirement described in the criterion.
- **GPT-5.5: Fail.** The memo discusses Section 6.5 block-billed research entries and says to count entire entries toward the research cap unless allocated, but it does not articulate the specific requirement that at least 50% of the time be allocated to the non-research component or the entire entry will be reduced to the research cap rate.

### C-026

Issue 9: Identifies Westlaw disbursement charge as prohibited ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L218))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the $4,850.00 Westlaw charge in Section 4 (Disbursements) and recommends to 'Disallow in full under §9.3. Legal research database subscriptions are included in hourly rates and cannot be passed through.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly flags the $4,850.00 Westlaw online legal research disbursement in the disbursements section and states it should be disallowed in full under §9.3 because legal research database subscriptions are included in hourly rates and cannot be passed through.

### C-027

Issue 9: Recommends $4,850 adjustment for Westlaw disbursement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L226))

- **Sonnet 4.6: Pass.** The memo explicitly states under Section 4 (Disbursements) for Westlaw online legal research: 'Disallow in full under §9.3. Legal research database subscriptions are included in hourly rates and cannot be passed through.' The amount listed is $4,850.00, which matches the criterion exactly.
- **GPT-5.5: Pass.** The memo expressly identifies the Westlaw online legal research disbursement as $4,850.00 and recommends disallowing it in full, which is the required adjustment.

### C-028

Issue 10: Identifies inter-matter duplicative MTCA research with DOE Matter ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L234))

- **Sonnet 4.6: Pass.** Section 2.3 of the memo explicitly addresses cross-matter MTCA research duplication under Section 6.6. It identifies Takahashi's July 1-2 Cascade MTCA contractor-liability and CERCLA-analog entries overlapping with DOE invoice Takahashi entries on July 1 (3.0h/$1,020), July 2 (2.5h/$850), and July 8 (2.0h/$680), totaling $2,550. The memo cites Section 6.6 (Inter-Matter Research prohibition) and recommends crediting the duplicate charges. While the memo doesn't explicitly state '9.5 hours' for Cascade or '12.5 hours' for DOE, it does identify the specific overlapping Takahashi entries across both matters for MTCA contractor-liability/CERCLA research and applies Section 6.6. The criterion is substantially met.
- **GPT-5.5: Pass.** The memo expressly identifies cross-matter MTCA/CERCLA research duplication between the Cascade litigation invoice and the DOE matter, cites Section 6.6, names Takahashi’s DOE entries, and discusses overlapping Cascade July 1–5 Takahashi/Wendt MTCA research. Although it does not explicitly state the Cascade July 1–2 Takahashi total as 9.5 hours, it identifies the required inter-matter duplication issue and the DOE overlap totaling 12.5 hours when including the additional July 15 and July 22 entries flagged for review.

### C-029

Issue 10: Cites Section 6.6 for inter-matter research prohibition ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L242))

- **Sonnet 4.6: Pass.** Section 2.3 of the memo explicitly states 'Section 6.6 requires research that benefits multiple TerraVerde matters to be billed only once, to the primary matter' and later in Section 6 the recommended response cites '§§6.4 and 6.6' for cross-matter research credits. The memo clearly cites Section 6.6 in connection with the inter-matter duplicative research issue.
- **GPT-5.5: Pass.** The memo expressly addresses 'Cross-matter MTCA research' and states that 'Section 6.6 requires research that benefits multiple TerraVerde matters to be billed only once...' It also references §§6.4 and 6.6 in the recommended response for duplicative research across matters.

### C-030

Issue 11: Identifies arithmetic error in research efficiency discount ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L250))

- **Sonnet 4.6: Pass.** The memo explicitly states in Section 1: 'Research efficiency discount: $7,732.00, described as 15%. 15% of $54,104.50 is $8,115.68; stated discount is short by $383.68.' This directly identifies the arithmetic error in the research efficiency discount, matching the criterion exactly.
- **GPT-5.5: Pass.** The memo explicitly states that the research efficiency discount is $7,732.00 described as 15%, but 15% of $54,104.50 is $8,115.68, making the stated discount short by $383.68.

### C-031

Issue 11: Calculates correct discount amount (~$8,115.68) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L258))

- **Sonnet 4.6: Pass.** The memo explicitly states: '15% of $54,104.50 is $8,115.68; stated discount is short by $383.68.' This matches the criterion requiring the correct discount amount to be approximately $8,115.68.
- **GPT-5.5: Pass.** The memo explicitly states that 15% of $54,104.50 is $8,115.68 and that the stated $7,732.00 discount is short by $383.68.

### C-032

Issue 12: Identifies duplicative unjust enrichment research (July 23-24) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L266))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the unjust enrichment duplication in Section 2.2: 'Unjust enrichment: Takahashi July 24, 3.5h/$1,190; Osei July 23, 4.0h/$1,180. $1,190.00 — Same Washington unjust-enrichment claim/defense framework. Section 6.4 treats elements and defenses as the same issue absent a demonstrated distinct legal framework; retain Osei's lower-rate work.' This directly matches the criterion's requirement to flag the overlap between Osei (July 23, 4.0 hrs) and Takahashi (July 24, 3.5 hrs) on unjust enrichment research under Section 6.4.
- **GPT-5.5: Pass.** The memo expressly flags the unjust enrichment overlap: Amara Osei on July 23 for 4.0 hours and Kenji Takahashi on July 24 for 3.5 hours, both researching Washington unjust-enrichment issues, and cites Section 6.4 duplicative research principles.

### C-033

Issue 13: Flags July MTCA research as potentially duplicative of June work ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L274))

- **Sonnet 4.6: Fail.** The criterion requires the memo to specifically note that the June 2024 invoice already included approximately 14.5 hours of MTCA research (8.0 hrs Wendt + 6.5 hrs Takahashi) supporting the summary judgment motion filed June 14, and to question whether the approximately 16.7 additional hours of MTCA research in July (Takahashi 9.5 hrs + Wendt 7.2 hrs) is genuinely incremental or largely redundant. The agent's memo does raise the concern about July MTCA research being duplicative of June work — it mentions the June 28 email warning, notes that 'The Cascade team had already researched and briefed the MTCA contractor-liability issue in June,' and flags that July MTCA entries 'repeat the issue already addressed in June.' However, the memo does not cite the specific June hours (8.0 hrs Wendt + 6.5 hrs Takahashi = 14.5 hrs) or the specific July hours breakdown (Takahashi 9.5 hrs + Wendt 7.2 hrs = 16.7 hrs) as required by the criterion. The criterion specifically requires these numerical details to be present for a PASS verdict.
- **GPT-5.5: Pass.** The memo does raise the cross-month MTCA duplication concern, stating that the Cascade team had already researched and briefed the MTCA contractor-liability issue in June and that July MTCA research should be justified as incremental rather than redoing existing work. Although it does not recite the precise 14.5 June hours and 16.7 July hours breakdown, it flags the required issue of July MTCA research potentially duplicating June work.

### C-034

Issue 13: Acknowledges reply brief may justify some additional research ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L282))

- **Sonnet 4.6: Pass.** The memo references the June 28 email warning about MTCA duplication and states that July MTCA research should 'build on work already completed.' In Section 2.4, it says to 'retain only supported incremental reply-brief work' and mentions 'July 9 Hargrove MTCA-preemption/contractor-defense research likewise need a specific explanation of the new issue arising from Cascade's June 28 opposition.' This acknowledges that some additional research may be justified by the reply brief context while still questioning the volume. The memo does raise the prior-month duplication concern. However, the criterion specifically requires acknowledgment that the reply brief filed July 19, 2024 may justify some additional MTCA research. The memo does reference 'reply-brief work' as potentially retainable and mentions 'new issue arising from Cascade's June 28 opposition,' which implicitly acknowledges the reply brief context. The memo both raises the prior-month duplication concern and acknowledges that incremental reply-brief work may be justified, satisfying both prongs of the criterion.
- **GPT-5.5: Pass.** The memo expressly raises the prior-month duplication concern for MTCA research and, while questioning repeated July MTCA work, states that TerraVerde should “retain only supported incremental reply-brief work.” This acknowledges that some additional July research may be justified by reply-brief needs while still challenging excessive or duplicative volume.

### C-035

Distractor 5: Does not flag litigation database hosting as improper ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L290))

- **Sonnet 4.6: Pass.** The memo addresses the Evergreen litigation database charge (Cascade D-10, $3,325.00) by conditioning payment on proof of vendor approval and actual cost with no markup, requesting a vendor invoice under §9.6. It does NOT disallow or reduce this charge as a billing guidelines violation (unlike the Westlaw charge which is disallowed in full under §9.3). The memo treats the two charges differently - Westlaw is outright disallowed, while Evergreen is held pending documentation. This satisfies the criterion that the memo should not recommend reducing or disallowing the litigation database hosting charge as a billing guidelines violation.
- **GPT-5.5: Pass.** The memo distinguishes the Evergreen litigation database hosting charge from the Westlaw charge. It disallows Westlaw under §9.3, but for the $3,325 Evergreen charge it only conditions payment on vendor approval, actual cost/no markup, and invoice support under §9.6; it does not recommend reducing or disallowing it as an improper database hosting charge.

### C-036

Memo states correct invoice total amount ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L298))

- **Sonnet 4.6: Pass.** The memo states in Section 1: 'The invoice's total due of $387,420.50 depends on the unreconciled fee summary' and also references '$341,820.50' as the reported net fees and '$45,600.00' as the disbursement total. All three figures are present and correct.
- **GPT-5.5: Pass.** The memo explicitly states the invoice's total due as $387,420.50 and also separately identifies $341,820.50 in net fees and $45,600.00 in disbursements.

### C-037

Memo includes a summary table of all recommended adjustments ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L306))

- **Sonnet 4.6: Fail.** The memo contains multiple tables throughout the document covering specific categories (research cap, duplicative entries, disbursements, other fee adjustments), but it does not include a single consolidated summary table that aggregates all recommended adjustments with dollar amounts and a total recommended reduction. The 'Bottom line' section lists action items in bullet form but does not provide a consolidated table with all adjustments and a grand total. The criterion specifically requires a summary table consolidating ALL recommended adjustments with a total recommended reduction, which is absent.
- **GPT-5.5: Fail.** The memo contains several issue-specific tables and dollar amounts, but it does not provide a consolidated summary table or clearly formatted list of all recommended adjustments with a total recommended reduction. It expressly avoids calculating a final net credit.

### C-038

Memo includes severity assessments for identified issues ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L314))

- **Sonnet 4.6: Fail.** The memo does not assign any severity ratings (such as Critical, Significant, Minor, or equivalent priority rankings) to the identified issues. While the memo is detailed and well-organized by category, it uses no severity classification system. Issues are described and quantified but never labeled by priority or severity level.
- **GPT-5.5: Fail.** The memo identifies many issues and recommends actions, but it does not assign explicit severity ratings or an equivalent priority ranking system (e.g., Critical/Significant/Minor) to the major issues.

### C-039

Issue 2: Cites Section 6.3 for partner research restriction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L322))

- **Sonnet 4.6: Pass.** The memo explicitly cites Section 6.3 in connection with partner research billing. In section 2.1, it states 'Section 6.3 bars partner research at partner rates' and later references 'Sections 4.1 and 6.3' when discussing Samantha Ortega's research entries. The criterion is satisfied.
- **GPT-5.5: Pass.** The memo explicitly states in Section 2.1 that “Section 6.3 bars partner research at partner rates” and applies that provision to the partner-coded research entries.

### C-040

Issue 3: Cites Section 6.4 for duplicative MTCA research ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L330))

- **Sonnet 4.6: Pass.** The memo explicitly cites Section 6.4 in section 2.2 ('Duplicative research within Cascade') and in the MTCA contractor liability entry: 'Section 6.4 requires payment only for the most junior qualified attorney's research when different attorneys research the same or substantially overlapping issue in the same billing period.' The MTCA contractor-liability duplication (Wendt July 1/5 and Takahashi July 1-2) is the first entry in the duplication table, and Section 6.4 is cited as the basis throughout that section.
- **GPT-5.5: Pass.** The memo expressly cites Section 6.4 in the duplicative research section and applies it to MTCA contractor-liability research across Wendt and Takahashi, recommending retention of the most junior qualified researcher’s work.

### C-041

Issue 7: Cites Section 4.3 for onboarding/get-up-to-speed entries ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L338))

- **Sonnet 4.6: Pass.** The memo explicitly cites §4.3 in Section 2.4 when discussing the 'get up to speed' and 'familiarize with' entries: 'The engagement letter lists Wendt as assigned since January, so §4.3's onboarding prohibition applies only if H&L confirms he was newly/rotationally assigned; if so, the July 25 orientation component is nonbillable in full.' This directly connects Section 4.3 (New Attorney Onboarding) to the background/familiarization entries.
- **GPT-5.5: Pass.** The memo discusses the Wendt entries for 'familiarize' and 'get up to speed' in the same bullet and expressly cites “§4.3's onboarding prohibition,” noting the orientation component would be nonbillable if applicable. Thus Section 4.3 is cited in connection with those onboarding/get-up-to-speed entries.

### C-042

Issue 9: Cites Section 9.3 for Westlaw disbursement violation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L346))

- **Sonnet 4.6: Pass.** The memo explicitly cites Section 9.3 in the disbursements table for the Westlaw charge: 'Disallow in full under §9.3. Legal research database subscriptions are included in hourly rates and cannot be passed through.'
- **GPT-5.5: Pass.** The memo explicitly identifies the Cascade Westlaw online legal research disbursement and states: “Disallow in full under §9.3. Legal research database subscriptions are included in hourly rates and cannot be passed through.” This cites Section 9.3 in connection with the Westlaw charge.

### C-043

Summary table total reflects aggregation of individual adjustments ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L354))

- **Sonnet 4.6: Fail.** The agent's output does not contain a summary table that aggregates individual adjustments into a stated total. The memo presents various recommended reductions across multiple sections (research duplication: $13,482.50; partner rate reductions: $3,185.00 + $1,375.00; cross-matter MTCA: $2,550; vague/background research: $4,152.50; travel time: $3,265.00; deposition attendance: $885.00; transcript summaries: $1,750.00; Westlaw: $4,850.00; etc.) but explicitly warns against simply adding them together and does not provide a summary table with a grand total. Since there is no summary table with a stated total to verify against individual line items, the criterion — which requires that a summary table total reflects the aggregation of individual adjustments and that the arithmetic is correct — cannot be satisfied. The absence of such a summary table means the criterion fails.
- **GPT-5.5: Fail.** The output does not provide a final summary table with a stated total recommended reduction aggregating all individual adjustments. Although several intermediate subtotals shown appear arithmetically correct, the specific criterion concerns whether a summary-table total equals the sum of listed adjustments, and that required aggregate total is absent.

### C-044

Issue 4: Recommends dollar adjustment for damages research duplication ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L362))

- **Sonnet 4.6: Pass.** The memo explicitly addresses consequential damages duplication in Section 2.2: 'Consequential damages: Takahashi July 3, 3.5h/$1,190; Osei July 8--10, 13.0h/$3,835.00. Recommended credit (gross): $1,190.00.' It also addresses lost profits duplication: 'Lost profits: Wendt July 18, 4.5h/$1,912.50; Takahashi July 18, 3.5h/$1,190. Recommended credit (gross): $1,912.50.' Both involve Osei, Wendt, and/or Takahashi and recommend specific dollar adjustments for duplicative research.
- **GPT-5.5: Pass.** The memo expressly identifies duplicative consequential damages research by Takahashi and Osei and recommends a $1,190 credit, and duplicative lost profits research by Wendt and Takahashi with a $1,912.50 credit. This satisfies the requirement to recommend a dollar adjustment for damages research duplication.

### C-045

Issue 6: Recommends dollar adjustment for spoliation/ESI duplication ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L370))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the spoliation/ESI sanctions duplication in Section 2.2, identifying Briggs July 2 (2.5h/$1,812.50) and July 24 (1.5h/$1,087.50), Wendt July 29 (2.8h/$1,190), and Takahashi July 29 (4.3h/$1,462) as overlapping entries on the same federal spoliation/sanctions framework. The recommended credit is $4,090.00 gross, retaining Takahashi's lower-rate work and removing the partner and Wendt overlap. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly identifies duplicative “Spoliation / ESI sanctions” research, including the July 29 Wendt and Takahashi overlap, and recommends a dollar credit of $4,090.00 for that duplication.

### C-046

Osei's July 19 background research flagged as potentially non-billable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/task.json#L378))

- **Sonnet 4.6: Pass.** The memo explicitly flags Osei's July 19 entry (5.0 hours/$1,475.00) for 'technical industry/background research' in Section 2.4, noting it does not identify a specific legal question and its purpose as required by §6.5, and recommends disallowing the $4,152.50 (which includes this entry) absent a corrected, substantive explanation. This satisfies the criterion of flagging the entry as potentially non-billable background/familiarization research, even though it cites §6.5 rather than §4.3.
- **GPT-5.5: Pass.** The memo expressly identifies Osei's July 19 entry for 5.0 hours/$1,475 as technical industry/background research and recommends disallowing it absent a substantive explanation, flagging it as problematic background/familiarization research.

# Item 11: lrb-dcca-challenge-police-discipline-assignment-3 — criterion_16

Bottom line: John's call (Not defective, AI reasoning Wrong, environment Correct) holds up. The discrepancy the criterion rewards is real and confirmed in the pinned PDFs (PERB Decision p. 1 ¶ 1 says "40-day"; Award p. 2 ¶¶ 9–10 say "45-day"), and the prompt itself points solvers to it by asking them to anchor arguments in "specific findings of the Award and the PERB Decision." The main weakness is in the note, not the verdict: it rests on "desirable training signal" rather than the protocol test, and it concedes that the point goes "beyond the prompt" without saying why a competent lawyer would reasonably infer it. I recommend a note-only revision that ties the point to the prompt's anchoring instruction and to the record-engagement argument criteria 7 and 11 reward. No field change.

## John's recorded call

- **Rubric verdict:** Not defective
- **AI reasoning:** Wrong
- **Defect basis / Defect arises from environment:** blank (correct for a Not defective verdict)
- **Environment:** Correct; explanation blank
- **Note (in brief):** "Rubric is correct." Flagging that PERB states a 40-day suspension when the Award imposed 45 days "is not necessarily essential" but "does improve an internal memo." It is a "desirable training signal" even if Sol "is technically correct that this is training the model to go beyond the prompt somewhat."
- **Sources:** PERB Decision ¶ 1 ("reduced the penalty of termination to a 40-day suspension without pay") and ¶ 7 ("affirmed in all respects"); Award ¶ 10 ("reduced to a 45-day suspension without pay").

## Strongest objections

1. **Defect basis (c): an unrequested requirement that costs a competent response 10% of the positive points.** This is GPT-6 Sol's blind finding (task directory `gpt-6-sol-audit.md`, F1). The assignment 3 prompt asks for (1) MPD's strongest contrary-to-law arguments and the DCCA standard of review and (2) the public-policy test, the policy to invoke, its application, and the weakest point in each argument. It does not ask for a record-accuracy check. A response that uses the correct 45-day figure throughout, as the prompt itself does ("reduced Officer Colin Braddock's termination ... to a 45-day suspension"), and analyzes both exceptions well would lose 6 of 60 positive points. That is three times the weight of the core rule criteria (criteria 1, 2, 4, 5 and 6 are 2 points each). PERB's order affirms the Award "in all respects" (PERB Decision p. 2 ¶ 7), so the operative remedy is not in doubt. GPT-6 Luna's own answer, which met the criterion, says "the discrepancy does not change the statutory analysis" (`model-runs/.../gpt6luna-xhigh/response.md`, line 67).
   - *Does the note answer it?* Partly. John concedes the first element of basis (c) ("go beyond the prompt somewhat") but does not address the second: whether a competent lawyer "would not reasonably infer" the requirement. His answer is policy (it is a good thing to train) rather than the protocol test (would the criterion misgrade a permissible competent response?). The answer exists in the record (see "Stronger arguments" below), and the note should use it. Point weighting is not itself a defect basis under the protocol, which asks whether the criterion grades the point it covers correctly, so the 6-point weight does not change the verdict.

2. **Arguable rather than Not defective.** Someone defending Sol's "arguable" label could say that reasonable litigators would disagree about whether omitting a harmless clerical slip makes a memo incompetent, which is the protocol's definition of Arguable. John's own "not necessarily essential" invites this.
   - *Does the note answer it?* Not directly. The better answer is that the protocol treats "a demanding but defensible standard" as Not defective, and a criterion that rewards a true, record-anchored fact the prompt directs the solver toward is demanding rather than wrong. The record here is very short: the PERB Decision runs seven paragraphs, and the misstatement is in the first one. A careful associate told to anchor arguments in PERB's findings would read ¶ 1 and compare it with the Award, which is in the accumulated attachments from assignment 1. Treating the omission as a small lapse in close reading, rather than as a competent alternative approach, is reasonable. I would not change the verdict. If the item were re-decided as Arguable, the Defective count (21 of 25) and the estimate would not move, because only Defective verdicts count.

3. **The deliverable is not an "internal memorandum."** The assignment 3 prompt does not specify a form. Assignment 2 asked for "a draft memorandum section," and assignment 3 asks the firm to assess whether a petition for review "is viable," so John's characterization is fair as context but is not stated in this prompt. It does not affect the verdict. The point holds a fortiori for a brief: a petition for review must describe the decision below accurately, so counsel needs to know that PERB misdescribed the remedy.

4. **Environment: an objective error in the supplied record?** PERB's "40-day" is a factual error in a supplied document. Under the protocol, "Planted mistakes that the task asks the solver to catch are not environment defects." The prompt does not expressly ask solvers to catch it, but the criterion rewards catching it, cites both locators in its source field, and the upstream justification ties it to the anchoring instruction, so it is plainly planted. John's environment verdict of Correct is right. A one-line explanation would forestall the objection, although the protocol requires an explanation only when the environment is Defective.

I found no misreading of the record, no overlooked stipulation (the three stipulations concern comparators and notice and do not touch the suspension length), and no closed-universe problem: both documents are in the assignment 3 universe (the Award is listed again in the assignment 3 prompt).

## Stronger arguments for the call

- **The prompt's own words point to the discrepancy.** Question 1 directs: "Anchor each argument in specific findings of the Award and the PERB Decision, with page and paragraph citations." The PERB Decision's description of what the Award did (¶ 1) is one of those findings, and it is wrong. A response that cites PERB ¶ 1 for the procedural history without catching the error would repeat a misstatement, which is a real drafting risk in this exercise.
- **The discrepancy supports an argument the rubric rewards.** Criterion 7 (PERB "affirmed the Award without addressing MPD's specific contrary-to-law arguments") and criterion 11 (PERB's "unexplained rejection ... undermines the deference its interpretation would otherwise receive") build MPD's best answer to the deferential standard in *FOP/DOC Labor Comm. v. PERB*, 973 A.2d 174 (D.C. 2009) (fop_doc_labor_comm_v_perb_2009.pdf, PDF p. 3: "This court will not easily disturb a decision of the PERB"; "Unless 'rationally indefensible,' a PERB decision must stand"). The same opinion notes that the court "may not 'affirm on a ground not relied on by the agency'" (PDF pp. 5–6, n. 2). PERB's misstatement of the very penalty it affirmed "in all respects" is concrete, record-anchored evidence that PERB did not engage closely with the Award. Claude Opus 5.5's saved answer used it exactly that way ("it supports the argument ... that PERB did not engage closely with the Award," `model-runs/.../opus55-low/response.md`, line 44; see also line 245).
- **The expected answer is fully supported by the record.** The pinned PDFs confirm "40-day suspension without pay" at PERB p. 1 ¶ 1 and "45-day suspension without pay" at Award p. 2 ¶ 9 and ¶ 10 (¶ 10 also deducts "the 45-day suspension" from back pay). The prompt itself says 45 days. No reading of the record makes 40 days correct.
- **Opus's blind pass considered and declined to flag this criterion** on the same ground ("a real discrepancy relevant to anchoring arguments in PERB's findings," `claude-opus-5-5-audit.md`, coverage note), and the reconciliation overturned Sol's flag for the same reasons. Those are AI arguments, not independent verification, but they show the anchoring rationale is the natural reading of the criterion.
- **Both saved model runs met the criterion 3/3**, which shows the point is reachable without being told to look for it. This does not prove the criterion is right; it does show it does not demand something a capable reader would not find.

## Errors in the note

- No factual or citation errors. The three quotations match the pinned PDFs (PERB p. 1 ¶ 1; PERB p. 2 ¶ 7; Award p. 2 ¶ 10, whose full sentence is "The penalty of termination is reduced to a 45-day suspension without pay").
- The note gives paragraph but not page numbers. The prompt requires page-and-paragraph citation, so the sources line would be cleaner as PERB Decision p. 1 ¶ 1 and p. 2 ¶ 7; Award p. 2 ¶¶ 9–10.
- "Internal memorandum" is a fair inference from the matter, not something the assignment 3 prompt states (see objection 3).
- The reasoning is framed as "training signal" rather than the protocol's test. That is a framing issue, not an error, but it leaves the (c) objection only half-answered on the face of the note.

## Recommended fields

| Field | John's value | Recommended | Note |
|---|---|---|---|
| Rubric verdict | Not defective | Not defective | Demanding but defensible; the expected answer is a true record fact the prompt directs the solver toward. |
| AI reasoning | Wrong | Wrong | Required for Not defective; Sol's (c) reason does not hold up. |
| Defect basis | blank | blank | Not applicable. |
| Defect arises from environment | blank | blank | Not applicable. |
| Environment | Correct | Correct | The 40-day misstatement is a planted error the criterion rewards catching. |
| Environment explanation | blank | optional one line | Not required for Correct; see the suggested revision. |
| Note | as recorded | revise (below) | Reframe in protocol terms and add locators. |

**Change classification: note-only.** The fields agree with each other and with the note. No tally effect.

## Defect basis and environment origin

Not applicable: the verdict is Not defective. On the environment: the PERB Decision's "40-day" is wrong as a matter of record, but it is a planted mistake the criterion rewards the solver for catching, so under the protocol it is not an environment defect. I found nothing else in the assignment 3 materials that changes this. The matter's citation check notes that the prompt and PERB Decision frame "contrary to law" and "public policy" as separate exceptions although D.C. Code § 1-605.02(6) is conjunctive ("contrary to law and public policy"). The check treats that as imprecise rather than a decisive error, and it does not bear on this criterion.

## Suggested revision of the note

> Rubric is correct. The criterion rewards pointing out that the PERB Decision says the Award reduced Braddock's termination to a "40-day suspension" (perb_decision_braddock.pdf p. 1 ¶ 1), when the Award imposed 45 days (braddock_arbitration_award.pdf p. 2 ¶¶ 9–10). Sol's point is that the prompt did not specifically ask for this. But the prompt does tell the solver to "[a]nchor each argument in specific findings of the Award and the PERB Decision," and PERB's description of what the Award did is one of those findings. A careful lawyer reading PERB's seven short paragraphs against the Award would notice the error and would want the client to know about it, both so the brief does not repeat it and because a Board that misstated the very penalty it affirmed "in all respects" (p. 2 ¶ 7) gives MPD concrete support for the argument, rewarded by criteria 7 and 11, that PERB's cursory affirmance deserves less deference. It is not essential to the statutory analysis, and the operative remedy is still 45 days, but rewarding it is a demanding, defensible standard, not a misgrade. It is also the kind of thing you want a model to flag even when the user did not think to ask. Environment: the 40-day figure is a planted error the criterion rewards catching, not an environment defect.

## What could not be verified

- Whether micro1 intended the 40-day figure as a trap is inferred from the criterion itself; no upstream design note says so. The real PERB decision in the apparent source case (Officer Michael Thomas) was not checked for a similar misstatement, because it would not change the analysis of the task as given.
- I did not independently re-run any grader. The native grades are reported as saved.
- For context only: assignment 4 later introduces a "Kucera comparator" that resulted in a 40-day suspension (pinned assignment 4 `rubric.json`). I did not assess whether that later figure relates to PERB's misstatement. It does not bear on assignment 3.

## Sources consulted

- Worksheet entry: `docs/legalreasonbench-audit/litigation/human-review/worksheet.md`, section "## 11." (criterion, source note, justification, attachments, blind findings, reconciliation, native grades, review block).
- Protocol: `docs/legalreasonbench-audit/litigation/human-review/README.md` (definitions; basis (c); planted mistakes and environment defects; "demanding but defensible standard").
- Tally: `docs/legalreasonbench-audit/litigation/human-review/stress-test/tally-at-review-start.txt`.
- Task: `docs/legalreasonbench-audit/litigation/tasks/lrb-dcca-challenge-police-discipline-assignment-3/input.json` (all 16 criteria; research universe closed-universe; current prompt and both prior prompts), `upstream-instruction.md`, `gpt-6-sol-audit.md` (F1), `claude-opus-5-5-audit.md` (coverage note), `reconciliation.md`.
- Pinned PERB Decision: [perb_decision_braddock.pdf](https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-3/workdir/attachments/perb_decision_braddock.pdf), p. 1 ¶¶ 1–4, p. 2 ¶¶ 5–7 (text layer extracted and confirmed).
- Pinned Award: [braddock_arbitration_award.pdf](https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-1/workdir/attachments/braddock_arbitration_award.pdf), p. 2 ¶¶ 7–10 (text layer extracted and confirmed).
- Pinned rubric: [assignment 3 rubric.json](https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-dcca-challenge-police-discipline/steps/assignment-3/tests/fixtures/rubric.json#L180); assignment 4 and 5 rubrics checked for related criteria.
- *Fraternal Ord. of Police/Dep't of Corr. Lab. Comm. v. D.C. Pub. Emp. Rels. Bd.*, 973 A.2d 174 (D.C. 2009), as uploaded (fop_doc_labor_comm_v_perb_2009.pdf, PDF p. 3 standard of review; PDF pp. 5–6 n. 2); the uploaded copy is a print of [FindLaw](https://caselaw.findlaw.com/court/dc-court-of-appeals/1136095.html), which the matter citation check compared against the official text.
- D.C. Code § 1-605.02(6), as uploaded (dc_code_1-605.02.pdf, PDF p. 1); current text at [code.dccouncil.gov](https://code.dccouncil.gov/us/dc/council/code/sections/1-605.02).
- Citation check: `docs/legalreasonbench-audit/litigation/citation-check/results/lrb-dcca-challenge-police-discipline.md` (FOP verification; conjunctive "law and public policy" note).
- Saved model runs: `docs/legalreasonbench-audit/litigation/model-runs/lrb-dcca-challenge-police-discipline-assignment-3/gpt6luna-xhigh/response.md` (line 67) and `opus55-low/response.md` (lines 44, 245, 387).

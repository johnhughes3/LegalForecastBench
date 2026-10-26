# Consistency pass: Claude Fable 5.1

Reviewer: Claude Fable 5.1, run independently of the per-item stress tests and of the other consistency reviewer. Materials read: the protocol (`docs/legalreasonbench-audit/litigation/human-review/README.md`), every entry and review block in `docs/legalreasonbench-audit/litigation/human-review/worksheet.md`, `sample.json`, the tally at review start (`stress-test/tally-at-review-start.txt`), the task prompts and upstream preambles under `docs/legalreasonbench-audit/litigation/tasks/`, and the primary extractions named below. Nothing else under `stress-test/` was opened. Where a judgment turns on what a document says, I checked the extraction myself rather than relying on the AI reports.

## Bottom line

John applies one principle consistently across the 25 items: a criterion is Defective whenever he can describe a competent response that the criterion, read literally, would misgrade, regardless of how likely that response is or how many points are at stake. Applied that way, the Defective definition does nearly all the work and the Arguable category does none. The 21/0/4 split follows from that reading, not from inconsistent coding. The reading is defensible on the protocol's text ("would either fail a response that a careful litigator would consider correct"), but it leaves no role for the protocol's second Arguable clause ("the problem would affect only unusual responses") or its materiality sentence ("borderline or low-impact concerns are Arguable"), and it departs from the Harvey rule that requiring one permissible option is not itself a defect. Several of John's own notes use the vocabulary of the Arguable definition ("really a judgment call," "a closer call," "perhaps narrowly correct") while recording Defective.

I found two genuine field inconsistencies and one definitional stretch that affect the environment table, none of which affects the headline estimate:

1. Item 16 records Environment: Correct while the six other sampled items in the same assignment (14, 15, 17–20) record Environment: Defective. The protocol makes the environment verdict an assignment-level fact. Clerical.
2. Item 23 records "Defect arises from environment: Yes" and Environment: Defective on a ground (the supplied Facts differ from the real case) that John coded the opposite way in item 10, and that the protocol does not treat as an environment error. Substantive for the "arising from the environment" count (9 → 8); it does not touch the estimate.
3. Items 24 and 25 record Environment: Defective for an ambiguous prompt, which is outside the protocol's definition of an environment defect (objective record errors, or materials that direct improper work product). Defensible as "Defect arises from environment," less so as an assignment-level Environment verdict.

The highest-leverage judgment is not an inconsistency but a single call applied to six items (14, 15, 17–20, the missing-affidavit set). The same principle produced the same result six times, so it is consistent; but it is the call on which the reconciliation and ordinary practice disagree most sharply, and moving it alone takes the estimate from 53 of 63 to 38 of 63. The honest treatment is a disclosed sensitivity table, not an edit.

Of the seven "Unambiguous objective error" codings, six are secure. Item 10 is coded Objective on a note written in professional-judgment terms; the Douglas text actually supports an objective ground, but the note does not lead with it.

## Per-item matrix

Fields: V = rubric verdict (D Defective, ND Not defective); AI = AI reasoning (C Correct, W Wrong); B = basis (Obj / PJ); O = defect arises from environment; E = environment verdict. "Principle" is the rule John actually applied, in my words.

| # | Assignment, criterion | Dir, pts | Universe | V / AI / B / O / E | Principle John applied | Consistency concern |
|---|---|---|---|---|---|---|
| 1 | land-use-1, DCI2018-10023 remained active | Penalty −15 | Open | D / C / Obj / No / Correct | Penalizing a statement the record makes, on a legal theory the cited code does not support (applicant-fault condition), is an objective error. | None. Basis differs from the other "States/Mentions" penalties (13, 16, 22) for a stated reason: here the rubric's premise is legally wrong and record-contradicted. Note relies in part on real-litigation party positions (see "Points to tighten"). |
| 2 | land-use-1, County should cease construction | Penalty −30 | Open | D / C / PJ / No / Correct | A penalty that rejects a recommendation the rubric's own authority supports fails a response a careful lawyer would consider correct (Harvey "rejecting a correct one"). | None. This is the paradigm case for the Harvey rule, and PJ is the right basis because the criterion penalizes a recommendation rather than stating a legal proposition. |
| 3 | land-use-1, file timely appeal to 6th DCA | +20 | Open | D / C / PJ / No / Correct | A reward tied to one strategy fails a competent memo that recommends another. | Arguable-boundary case. Note says "that's really a judgment call"; the real county did what the rubric asks. Harvey: "Requiring one permissible option is not by itself a defect." Reconciliation: arguable. |
| 4 | land-use-1, remand while appeal pending | +20 | Open | D / C / PJ / No / Correct | Same as 3; the "while an appeal is pending" clause entangles a correct recommendation (remand) with the debatable one. | Same as 3. Coded consistently with 3. |
| 5 | land-use-1, § 163.3167(10) safe harbor | +10 | Open | D / C / Obj / No / Correct | Statute text contradicts the rubric's proposition. | None. Clean objective. |
| 6 | land-use-1, withdrawn Feb. 13, 2020 under AC-2-6 | +5 | Open | D / C / Obj / No / Correct | Same as 1 (reward side of the same error). | None. Consistent with 1. |
| 7 | land-use-2, expert testimony is CSE | +5 | Open | ND / W / — / — / Correct | A point whose relevance is inferable from the supplied record is a defensible standard even if the underlying document is not uploaded. | None. Distinguished from 14–20 on a stated ground (existence of the evidence is shown in the record). Verified: Resolution recitals and Petition (Crespo exhibit). |
| 8 | land-use-2, staff report is CSE | +5 | Open | ND / W / — / — / Correct | Same as 7. | None. |
| 9 | dcca-1, comparator coverage years conflict | +28 | Closed | D / C / Obj / No / Correct | Record contradicts the rubric's asserted fact. | None. Verified: all four incidents and terminations fall within 2018–2021; Final Notice ¶ 19 repeats the window. |
| 10 | dcca-2, no uploaded authority requires MPD to prove comparability | +26 | Closed | D / C / Obj / No / Correct | A proposition that is narrowly true in the abstract but misleading on this record (MPD's own Final Notice rested on comparators; Douglas puts the penalty burden on the agency) is defective. | Basis is the least secure Objective (note says "perhaps narrowly correct," "highly vulnerable," "effectively does need to prove"). Both blind models and the reconciliation: arguable. Compare 23: same "real-case rule carried onto changed facts" pattern, coded O = No here and O = Yes there. |
| 11 | dcca-3, PERB misstates suspension length | +6 | Closed | ND / W / — / — / Correct | A true, record-anchored point a competent lawyer would flag is "demanding but defensible." | Result consistent with 7/8. Note reasons partly from training-signal desirability rather than the protocol test (note-only). |
| 12 | forum-1, Smith affidavit does not show Cook inconvenient | +5 | Closed | ND / W / — / — / Correct | The criterion takes the legally sound side of a point Langenhorst actually draws. | None. Verified in the uploaded Langenhorst text. |
| 13 | forum-1, Mentions Cook lacks interest | Penalty −30 | Closed | D / C / PJ / No / Correct | "Mentions" wording reaches a memo that recounts and rebuts the argument. | Arguable-boundary case: the penalty did not fire in either native run (0/3, 0/3). Protocol: "would affect only unusual responses" → Arguable. Coded consistently with 16 and 22. |
| 14 | forum-2, supported by Vance affidavit | +3 | Closed | D / C / PJ / Yes / Defective | Rewarding a brief that asserts sworn support the record shows does not exist nudges toward hazardous work product. | The six-item lever (14, 15, 17–20). Consistent across the six; disputed by the reconciliation; see "Arguable boundary." Environment verdict consistent with 15, 17–20 but not with 16. |
| 15 | forum-2, supported by Sara Davis affidavit | +5 | Closed | D / C / PJ / Yes / Defective | Same as 14, acknowledged as "a closer call." | Weakest of the six: a client residence affidavit is fully supported by the record (she "resides in Kane County"), and the assignment-1 rubric (criterion 10) rewards recommending exactly that affidavit. |
| 16 | forum-2, States 60.5% clearance rate | Penalty −30 | Closed | D / C / PJ / No / Correct | "States" wording penalizes stating a true record figure that the opposing motion relies on. | **Environment field conflicts with 14, 15, 17–20 (same assignment).** Verdict and basis are consistent with 13 and 22. |
| 17 | forum-2, supported by Montgomery affidavit | +3 | Closed | D / C / PJ / Yes / Defective | Same as 14. | Same as 14. |
| 18 | forum-2, Vance affidavit says DuPage inconvenient | +3 | Closed | D / C / PJ / Yes / Defective | Same as 14. | Same as 14. |
| 19 | forum-2, Montgomery affidavit says DuPage inconvenient | +3 | Closed | D / C / PJ / Yes / Defective | Same as 14. | Same as 14. |
| 20 | forum-2, Linwood affidavit says DuPage inconvenient | +3 | Closed | D / C / PJ / Yes / Defective | Same as 14. | Same as 14. |
| 21 | vicar-1, conspiracy precludes justification | +15 | Closed | D / C / Obj / No / Correct | Statute text (§ 702.11 does not list conspiracy; § 704.6(1) requires participation in a forcible felony) and the rubric's own justification for criteria 28/29 contradict the criterion. | None on the result. Note leads with an independence principle for which no Iowa authority was found; the textual and internal-inconsistency grounds are the objective ones (note-only). |
| 22 | vicar-1, Mentions intimidation plea | Penalty −5 | Closed | D / C / PJ / No / Correct | "Mentions" wording penalizes an accurate mention that sets the prior aside (fired 2/3 on Opus's drafting note). | Arguable-boundary case by magnitude (−5 of 175; reconciliation downgraded for low impact). Consistent with 13 and 16. |
| 23 | vicar-2, lack of evidence who fired first | +25 | Closed | D / C / Obj / Yes / Defective | Record contradicts the rubric (Facts p. 7: Nelson "opened fire as the Trailblazer approached"). | **Origin and environment conflict with item 10 and with the protocol's environment definition.** Facts.pdf is also in vicar-1's environment, where items 21–22 record Environment: Correct. Basis Obj is sound. |
| 24 | vicar-2, Nelson's car already stopped | +10 | Closed | D / C / PJ / Yes / Defective | Re-grading five assignment-1 criteria on a "supplement" fails a focused supplement a competent lawyer could reasonably produce. | Environment: Defective rests on prompt ambiguity, not a record error. The shared preamble ("final complete legal deliverable … Build on that analysis") is the same preamble forum-2 carries, where John does not treat it as ambiguous. Arguable-boundary case. |
| 25 | vicar-2, OTB group could have driven away | +15 | Closed | D / C / PJ / Yes / Defective | Same as 24. | Same as 24. Coded consistently with 24. |

## Genuine inconsistencies, prioritized

### 1. Item 16's Environment verdict conflicts with the rest of forum assignment 2 (clerical; environment table)

Items involved: 16 versus 14, 15, 17, 18, 19, 20.

Evidence. Protocol §3: "each item records whether its assignment's task environment is Defective or Correct … whether or not they touch the sampled criterion." John's environment explanation on 14, 15, 17–20 is an assignment-level statement ("No affidavit from any of the five physicians is provided in the environment, and the prompt does not instruct the model to create one"). Item 16 is the same assignment and records Environment: Correct with a blank explanation. The tally script (`scripts/legalreasonbench_review_sample.py`, environment block) counts the field per item and derives "assignments with a Defective environment" from the set of tasks with any Defective item; it does not check within-assignment agreement, so this was not caught.

Strongest defense of John's coding. He may have read the Environment field as "the environment problem relevant to this criterion," and the 60.5% penalty has nothing to do with the affidavits. That reading is natural but is not the protocol's.

Recommendation. Change item 16 to Environment: Defective with the same explanation as items 14, 15, 17–20, and note the change in the worksheet. **Clerical.** Effect: Task environment Defective 9 → 10, Correct 16 → 15; rubric-by-environment Defective row 9 | 12 → 10 | 11. No effect on the estimate, on "assignments with a Defective environment" (still 2 of 9), or on the "arising from the environment" count (item 16's origin stays No, consistent with item 1's treatment of a penalty-wording defect as a rubric-only defect).

### 2. Item 23's environment origin is coded opposite to item 10 on the same principle, and outside the protocol's environment definition (substantive for the origin count; environment table)

Items involved: 23 versus 10; also 21 and 22.

Evidence. John's own note on item 23 says "Related: item 10 is the other sampled criterion that carries a real-case rule onto changed task facts." In item 10 he coded the defect as rubric-only (origin No, Environment Correct), reasoning that "the rubric is essentially importing a proposition of law from the real case without recognizing that the task environment was changed." In item 23 the identical pattern (the rubric imports "unclear who fired first" from the real Eighth Circuit opinion; the supplied Facts say Nelson fired first) is coded origin Yes, Environment Defective, with the explanation that the supplied Facts "differ from the real record." Two protocol points cut against the item-23 coding. First, the environment verdict "turns on objective errors in the supplied record, or task materials that direct work product a competent litigator should not put before a court." Facts.pdf (p. 7, verified: "Nelson had his car parked … and had hidden in the bushes. … He opened fire as the Trailblazer approached. … A rolling gun battle ensued") is internally coherent; nothing in the record contradicts it. Second, the protocol expressly treats a fictional record that departs from the real world as not an error ("an instruction in a fictional or hypothetical record that a response can reasonably follow, even where it misstates real-world law"). Third, Facts.pdf is an assignment-1 attachment available in both vicar assignments; if its content were an environment error, items 21 and 22 (vicar-1, Environment: Correct) would be inconsistent with 23.

Strongest defense of John's coding. The task author's own assignment-1 penalty justifications assume "it is unclear which side fired first," so one can argue Facts.pdf contains an unintended error relative to the record the author meant to supply, and the defect "stems from an error in the supplied task materials rather than in the criterion alone." That is a fair reading of the origin field's wording, but it requires inferring the author's intent from the rubric rather than reading the record as supplied, which is the opposite of how John handled item 10.

Recommendation. Change item 23 to "Defect arises from environment: No." **Substantive field change.** Effect: "arising from the environment" 9 → 8; no effect on the estimate, the Defective count, or the objective-error count. For the Environment field: if the vicar-2 prompt-ambiguity ground on items 24–25 stands (see inconsistency 3), item 23 stays Environment: Defective at the assignment level but its explanation should be the 24–25 explanation (clerical); if that ground is withdrawn, item 23 becomes Environment: Correct. Report either as a disclosed post-tally correction with the reason, or, if John stands by his coding, as a reviewer disagreement with the environment definition stated.

### 3. Items 24 and 25 record an environment defect for an ambiguous prompt, which the protocol's environment definition does not reach (substantive or reporting; environment table)

Items involved: 24, 25 (and by extension 23's environment verdict).

Evidence. The environment explanation is that the assignment-2 prompt "does not say whether response2.md must be a full revised brief, yet the verifier reads only response2.md and re-grades five assignment 1 criteria on it." Verified: assignment-2 criteria 5–9 repeat assignment-1 criteria 10–14 word for word (65 of 135 points). But the protocol's environment verdict is limited to "objective errors in the supplied record, or task materials that direct work product a competent litigator should not put before a court." An ambiguous scope instruction is neither. It fits better under rubric-defect reason (c), "requires something the instructions did not ask for and that a competent lawyer would not reasonably infer," which is a rubric defect with origin arguably Yes ("error in the supplied task materials"), not an assignment-level Environment: Defective. Two further points. The upstream shared preamble (`tasks/lrb-vicar-trial-jury-instructions-assignment-2/upstream-instruction.md`, verified) reads: "Write the final complete legal deliverable for this assignment to `response2.md`. The verifier reads only that file. … your prior deliverable `response1.md` is also on disk. Build on that analysis as the prompt directs." The identical preamble appears in `tasks/lrb-forum-non-conveniens-response-assignment-2/upstream-instruction.md`, where John does not treat it as a source of ambiguity. And whether a competent lawyer "would not reasonably infer" that "final complete legal deliverable" means the full brief is exactly the kind of question the Arguable band exists for; John's note argues from "token inefficiency," which is a benchmark-design criticism rather than the protocol's misgrading test.

Strongest defense of John's coding. The user-facing email says only "supplement your brief," GPT-6 Luna's native run read it that way (a 1,500-word supplement that scored 0/3 on both items), and a harness that re-grades five earlier criteria on a supplement does, in practice, punish a reasonable reading. The origin field's text ("error in the supplied task materials") is broad enough to cover an instruction that misleads.

Recommendation. Keep "Defect arises from environment: Yes" if John wishes (defensible on the origin wording), but either (a) recode Environment to Correct on 24 and 25 (and 23, per inconsistency 2), or (b) keep Environment: Defective and add one sentence to the environment table's reporting disclosing that the vicar-2 environment verdict rests on instruction ambiguity rather than a record error. Option (a) is a **substantive field change** for the environment table: with inconsistency 1 applied as well, Task environment Defective becomes 7 (the forum-2 items 14–20), Correct 18, and "assignments with a Defective environment" 1 of 9. Option (b) is **reporting**. Neither touches the estimate.

### 4. The Arguable band is empty although several notes describe Arguable situations (reporting; Defective count)

See "The Arguable boundary" below for the analysis. The recommendation is a disclosed sensitivity table, not a silent recode.

### 5. Item 10's basis is coded Objective on a note written in judgment terms (note-only preferred; objective-error count)

See "The objective-error versus professional-judgment line" below.

## The objective-error versus professional-judgment line

The protocol defines Objective as "the record, the law, the cited authority, or arithmetic contradicts the rubric." Six of the seven Objective codings meet it cleanly, and I verified the contradiction in each:

- Item 1 and 6: AC-2-6 § 4.1B(1) deems an application withdrawn only "if the six month deadline is not met because of action or inaction of the Applicant/Appellant"; nothing in the record establishes applicant fault, and the Petition states the case "was left open until September 13, 2023."
- Item 5: § 163.3167(10) protects an unappealed development order against later invalidation of the regulations, and (10)(b) preserves certiorari; the Order quashed the rezoning on timely certiorari.
- Item 9: the comparator memo's window (2018–2021) contains all four incidents and terminations.
- Item 21: § 702.11's enumerated forcible felonies do not include conspiracy; § 704.6(1) requires "participating in a forcible felony"; and the rubric's own justification for criteria 28–29 rejects the parallel theory as circular (an internal inconsistency under reason (d)).
- Item 23: Facts p. 7 says Nelson opened fire first.

Item 10 is different in kind. The note's argument is contextual and probabilistic: the proposition is "perhaps narrowly correct as a general proposition of law," but MPD "effectively does need to prove" its comparators because failure "leaves MPD highly vulnerable." That is the language of professional judgment, and both blind models and the reconciliation rated the item arguable. There is, however, an objective ground available in the uploaded Douglas text that the note does not foreground: the agency's penalty decision "can be sustained … only if the agency establishes the facts on which that decision rests by the requisite standard of proof," penalty selection is "properly within its burden of persuasion," and once "the appellant challenges the severity of the penalty … the agency will be called upon to present such further evidence" (uploaded reprint pp. 333–34, verified). MPD's Final Notice ¶ 19 rested its penalty on four comparator cases, and Award ¶ 2 put the penalty in issue. Read together, an uploaded authority does require MPD to establish the facts of the comparators it relied on, which contradicts the criterion's categorical "no uploaded authority requires."

Recommendation. **Note-only** (preferred): rewrite the item-10 note to lead with the Douglas textual ground and the Final Notice ¶ 19 reliance, so the Objective label rests on a contradiction rather than on litigation risk. Alternatively, **substantive**: recode the basis to Professional judgment, which moves the objective-error count from 7 of 25 to 6 of 25 and the secondary lower bound from 11 to 9 of 63; report as a disclosed sensitivity. Either way, the AI-reasoning field (Correct) stands, because the Douglas burden ground is the one the models gave.

A smaller point on item 21 (**note-only**): the note's lead argument is that § 704.6(1) applies only to a forcible felony distinct from the one claimed as justified, supported by a Florida case and the observation that the contrary rule "would swallow the rule." The reconciliation found no Iowa decision either way. The objective basis should be stated as the enumerated-list text plus the rubric's internal inconsistency, with the independence principle as supporting reasoning.

The asymmetry between item 1 (Objective) and items 13, 16, 22 (Professional judgment), all of them "States/Mentions" penalties, is principled and should be explained in the reporting: in item 1 the rubric's premise is itself legally wrong and record-contradicted, while in 13, 16 and 22 the premise is sound (the point is a bad fact or irrelevant prior) and the defect is wording that over-reaches to responses that rebut or set the point aside.

## The Arguable boundary

The protocol's Arguable has two clauses: reasonable litigators could disagree about whether the criterion would misgrade a competent response, or the problem would affect only unusual responses. It adds that materiality is part of Defective and that "borderline or low-impact concerns are Arguable," and it adopts the Harvey rule that "Requiring one permissible option is not by itself a defect; rejecting a correct one is."

John's operative test, visible across the 21 Defectives, is: can I describe one competent response that this criterion, read as written, would misgrade? If yes, Defective. Under that test the Arguable band is empty by construction, because any criterion a reviewer flags will have some response it misgrades. The test is a legitimate reading of the Defective definition's first sentence, and it was applied consistently. But it does not engage the second Arguable clause (probability), the materiality sentence (magnitude), or the Harvey reward-versus-penalty distinction. The following items are where those protocol features would have pointed to Arguable, in descending order of their effect on the estimate:

- Items 14, 15, 17–20 (six items). The reconciliation found no defect: the prompt says "Please include all affidavits and information you referenced from Assignment #1," names the five physicians, and the assignment-1 rubric (criteria 10, 11 and 13, verified in `tasks/lrb-forum-non-conveniens-response-assignment-1/input.json`) rewards recommending exactly these affidavits, so the task design plainly contemplates drafting them. Drafting affidavits from facts a partner relayed, for witnesses to review and sign, is ordinary practice. John's contrary view rests on (i) reading "include" as limited to existing documents, (ii) reading "If a document is not uploaded, it does not exist" as a bar on drafting, and (iii) the professional-ethics hazard of a brief that asserts sworn support before execution. Point (iii) is real and his note documents it concretely from Opus's native output. Points (i) and (ii) are contestable: the same "does not exist" sentence appears in every closed-universe prompt as a research-universe limit, and nobody reads it to forbid drafting the brief itself. This is the paradigm of "reasonable litigators could disagree." Item 15 (a client residence affidavit, which the record fully supports and which assignment-1 criterion 10 asks for) is the weakest Defective of the six, and John's note says so ("a closer call").
- Items 3 and 4. The note says "that's really a judgment call," and the real county filed the appeal and remanded concurrently, as the rubric asks. A +20 reward for one permissible strategy does not "reject" the other in the Harvey sense; it fails to credit it. The reconciliation rated both arguable.
- Items 24 and 25. Whether "final complete legal deliverable … Build on that analysis" tells a competent lawyer to produce the full brief is a disagreement among reasonable readers (the reconciliation thought it decisive; John thinks it unclear).
- Item 13. The penalty did not fire in either native run; both runs recounted and rebutted the argument and all six judge votes cleared it. "Would affect only unusual responses" fits. The reconciliation rated it arguable.
- Item 22. A −5 penalty of 175 that fired on a drafting note. The reconciliation downgraded it to arguable for low impact, which is what the protocol's materiality sentence directs.
- Item 10. Both blind models and the reconciliation: arguable (see above).

Whether these are Defective or Arguable is a question the protocol leaves to the reviewer, and John's consistent answer is a legitimate one. The tally should not be edited on my account. What the protocol does require is honest reporting, and the cleanest form is a sensitivity table that shows the estimate under alternative codings. Computed with the protocol's exact one-sided 95% hypergeometric bound (N = 63, n = 25):

| Scenario | Defective | Proportion | Estimate of 63 | 95% lower bound |
|---|---|---|---|---|
| As tallied | 21 | 84% | 53 | 45 |
| Items 3, 4 → Arguable | 19 | 76% | 48 | 39 |
| Also 14, 15, 17–20 → Arguable | 13 | 52% | 33 | 24 |
| Also 24, 25 → Arguable | 11 | 44% | 28 | 20 |
| Also 10, 13, 22 → Arguable (equals the reconciliation's eight "problematic" items: 1, 2, 5, 6, 9, 16, 21, 23) | 8 | 32% | 20 | 13 |

The last row is a useful anchor because it is exactly the set the later reconciliation retained as problematic, so it can be described as "the reconciliation's view" without inventing a new category. Even on that floor, the review establishes that at least 13 of the 63 flagged criteria are defective, and the 45-of-63 figure is the reviewer's own considered view. Classification: **reporting**. If John chooses to recode any item after reading this, that is a **substantive field change** to be disclosed as such, with the pre- and post-change tallies both shown.

## Rubric versus environment defects

John distinguishes rubric defects from environment defects in the way the protocol asks in most places, and his two explicit cross-item distinctions are sound:

- Items 7–8 versus 14–20: he treats a missing document whose existence the record evidences (the staff report and expert testimony are recited in the Resolution and quoted in the Petition) as no bar to a criterion crediting its mention, while a missing document the record shows has not been created (the affidavits) is an environment problem. The distinction is stated in the item-14 note and applied consistently.
- Item 10 versus the environment: he correctly places the defect in the rubric, not the (internally coherent) altered record.

Three places depart from the protocol's definition or from each other, all discussed above: item 16 (environment verdict out of step with its assignment), item 23 (an internally coherent record coded as an environment error, contrary to item 10 and to the protocol's fictional-record rule), and items 24–25 (prompt ambiguity coded as an assignment-level environment defect). There is no sampled item where John found an environment-only defect (environment Defective, rubric Not defective); every Environment: Defective item is also origin Yes, and vice versa (9 of 9). That perfect alignment is itself worth a sentence in the reporting, because it means the environment table currently carries no information independent of the origin field.

On the forum-2 environment verdict itself: the protocol's second prong ("task materials that direct work product a competent litigator should not put before a court") is the only prong that fits, and it fits only if one accepts John's premise that the prompt directs a brief asserting unexecuted sworn support. The reporting should say so, because a reader who accepts the reconciliation's reading of the prompt will see forum-2 as a correct environment and the six items as rubric-only.

## Field-agreement problems

Mechanical checks, all 25 items: every Not defective item records AI reasoning Wrong and blank basis and origin fields (7, 8, 11, 12); every Defective item records a basis and an origin; every Environment: Defective item has an explanation; origin Yes and Environment Defective coincide on the same nine items; the tally lines reproduce from the recorded fields (21 Defective, 7 Objective, 9 origin Yes, 9 Environment Defective, 2 assignments), and I recomputed the hypergeometric bounds (45 of 63 for 21/25; 11 of 63 for 7/25).

AI reasoning Correct is justified on all 21 Defective items in the sense the protocol requires (a flagging model's blind stated reason is the actual defect). The one soft spot is item 10, where the models' reason (Douglas places the penalty burden on the agency) is part of John's ground but his principal ground (the task environment was altered from the real case so the proposition is irrelevant here) is new. Partly correct ("identified the right issue but misstated … the scope") would also be defensible. **Note-only.**

Notes agree with fields throughout, with two exceptions already covered: item 16 (environment explanation blank while the assignment's environment is recorded Defective elsewhere) and item 23 (the environment explanation describes a rubric-versus-real-case mismatch, not a record error).

## Proposed clearer groupings and explanations, mapped to existing fields

These are reporting devices built from recorded fields; none proposes a new field or category.

1. Defective criteria by underlying mistake. The protocol warns that "the count is of criteria, not independent mistakes." The 21 Defective criteria reduce to roughly 12 underlying mistakes, and a table makes the dependence visible:

| Underlying mistake | Items | Criteria | Basis | Origin | Reconciliation |
|---|---|---|---|---|---|
| AC-2-6 withdrawal theory | 1, 6 | 2 | Obj | No | problematic |
| Appeal-plus-remand as the only strategy | 3, 4 | 2 | PJ | No | arguable |
| Parkway Towers misread; pause penalized | 2 | 1 | PJ | No | problematic |
| § 163.3167(10) misapplied | 5 | 1 | Obj | No | problematic |
| Comparator date conflict that does not exist | 9 | 1 | Obj | No | problematic |
| Real-case burden rule carried onto changed facts | 10 | 1 | Obj | No | arguable |
| "States/Mentions" penalty wording reaching rebuttals | 13, 16, 22 (and 1) | 3 (+1) | PJ | No | arguable, problematic, arguable |
| Missing affidavits rewarded as existing support | 14, 15, 17–20 | 6 | PJ | Yes | not retained |
| Conspiracy plea as a § 704.6(1) bar | 21 | 1 | Obj | No | problematic |
| Real-case "unclear who fired first" carried onto changed Facts | 23 | 1 | Obj | Yes | problematic |
| Assignment-1 criteria re-graded on a supplement | 24, 25 | 2 | PJ | Yes | not retained |

2. Penalty versus reward criteria. All five sampled penalties (1, 2, 13, 16, 22) are Defective; 16 of 20 sampled rewards are. Four of the five penalty defects are the "States/Mentions" wording problem John already groups in his related-items lines. Reporting this split uses only the direction recorded in the worksheet header.

3. Open versus closed universe. Open-universe items (1–8): 6 Defective (3 Obj, 3 PJ), 2 Not defective, no origin Yes. Closed-universe items (9–25): 15 Defective (4 Obj, 11 PJ), 2 Not defective, 9 origin Yes. Every environment-origin defect is in a closed universe, which is what one would expect (a missing or altered document can only control the answer when the solver may not look elsewhere). One sentence in the reporting.

4. The sensitivity table above, keyed to the reconciliation's retained set, as the standard way of reporting the Arguable question without changing the tally.

5. A one-line explanation in the reporting of the basis asymmetry among the four "States/Mentions" penalties (item 1 Objective; 13, 16, 22 Professional judgment), as given above.

## Points checked and found sound

- The core test is applied the same way on every item: John asks what a careful litigator would write on the supplied record and whether the criterion as worded would misgrade it. I found no pair of materially similar situations coded differently on the rubric verdict itself. The one principle-level inconsistency (10 versus 23) is in the origin and environment fields, not the verdict.
- Items 1 and 6 are coded identically (penalty and reward sides of one error), as are 3 and 4, 14 and 17–20, and 24 and 25.
- Items 13, 16 and 22 are coded identically (Defective, PJ, origin No, Environment Correct) and the native-run evidence is reported candidly for each, including that 13 never fired.
- Items 7, 8, 11 and 12 (the four Not defectives) each take the "demanding but defensible" or "takes a reasonable side" branch of the protocol, with the distinguishing fact stated. I verified the Langenhorst distinction for item 12 in the uploaded text ("The defendant must show that the plaintiff's chosen forum is inconvenient to the defendant and that another forum is more convenient to all parties"), the Resolution recitals for 7–8, and the 40-day/45-day discrepancy for 11.
- The six clean Objective codings (1, 5, 6, 9, 21, 23) each rest on a document or statute I read and that contradicts the criterion.
- Item 2's basis (PJ rather than Objective) is right even though the rubric's authority says the opposite of what the source note claims, because the criterion penalizes a recommendation rather than stating a legal proposition; the misreading lives in a field the judge never sees.
- Item 15's note correctly identifies and sets aside the "Assignment #2" judge-visibility problem as a global issue rather than a per-criterion defect, and reports the label-scan denominator (10 of 1,074 votes).
- The sequential-assignment items (14–20, 24–25) are coded consistently with each other on origin and environment, and the notes identify the dependency explicitly.
- All field mechanics pass, and the tally reproduces.

Two notes to tighten (**note-only**, no field change): items 1, 3 and 6 lean on the real litigation's party positions and filings ("ground-truth evidence from the litigation"; the county's second-tier petition conceding likely mootness) as support. The protocol grades against the task as given; real-case material is context, and the notes should separate the basis (code text and record) from that context so a reader does not take the real-world positions as the ground of decision. Items 11, 24 and 25 reason partly from training-signal desirability and "token inefficiency"; the same conclusions can be stated in the protocol's terms (would a competent lawyer reasonably infer the requirement from the instructions), and should be.

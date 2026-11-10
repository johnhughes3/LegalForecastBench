# Assessment of the Codex review

Assessor: Claude Opus 5.5, the orchestrating agent. This file assesses `codex-review.md` (GPT-6 Sol, high reasoning effort, read-only, web search enabled; see `codex-run.md`) against the record and the governing authority. I checked each finding myself against the supplied documents, the saved model runs, the protocol, and the public sources noted below. Nothing in the worksheet or any other existing file was edited.

## Bottom line

Codex's review is careful and mostly correct. It understood the protocol's rubric-versus-environment distinction, the research universes, the penalty direction and the post-tally rule. I found no misreading of those. Every figure in its sensitivity table recomputes exactly under the protocol's hypergeometric method (N = 63, n = 25).

Most of its findings repeat points the consistency passes and per-item stress tests already made: the item 16 environment field, item 23's origin, item 10's basis, and the Arguable boundary for items 3–4, 15 and 24–25. On those it adds verified evidence rather than new grounds.

It adds three things the earlier reviews did not settle:

1. A verified passage from the real Eighth Circuit opinion that weakens item 23's environment explanation further.
2. A concrete argument that item 8's "recommending approval" predicate is not stated anywhere in the supplied record. I confirmed this, but I rate the finding only as partly holding.
3. A broader position that the VICAR assignment 2 environment should be Correct.

It made two small errors:

- It treated the 2019-era AC-2-6 text as unverifiable, although John's note cites the archived 11/17/15 text. I retrieved that text, and its § 4.1 heading and § 4.1B(1) match.
- It mislocated the citation-check row for item 4.

It also left one point on the table. The DCCA record has unplanted internal errors that bear on the environment field for items 9–11.

Only one recommendation qualifies as **clerical**: changing item 16's environment field to Defective, which moves the environment count from 9 to 10. Every other change is a **substantive** disagreement that can only be reported as a disclosed sensitivity, or a **note-only** correction. Codex's own bottom line keeps the frozen figures (21/25, 53 of 63, lower bound 45) as John's result and adds a sensitivity table. That matches the protocol and both consistency passes.

## Run caveats

- **Duration.** Codex finished in about 7 minutes on the first attempt and used 385,159 tokens. That is short for 25 items, but its citations show it opened the record extractions, the saved responses and the judge votes for the items it discussed.
- **Pinned binaries.** Codex says it "could not directly retrieve the pinned Hugging Face PDF/DOCX binaries". Its record-page findings therefore rest on the repository extractions.
- **Prior context.** Codex read its own local memory file at the start. The entries it found describe earlier Codex work in this repository (the model-run importer and the sampling procedure), not views on the 25 calls. It also read the earlier AI reviews, as invited. It is therefore an informed second opinion, not a blind one (`codex-run.md`).

## Findings

| # | Codex finding | Items | Assessment | Recommended classification |
|---|---|---|---|---|
| 1 | Item 16 environment field out of step with its assignment | 16 | Holds | Clerical |
| 2 | Item 23 origin should be No; "differs from the real record" unverified | 23 | Holds | Substantive (disclosed) |
| 3 | VICAR assignment 2 environment should be Correct; origin No on 24–25 | 23–25 | Partly holds | Reporting (preferred) or substantive |
| 4 | Item 10 basis should be Professional judgment; "handled in the same way" correction | 10 | Holds (basis); partly holds (wording) | Substantive (disclosed); note-only |
| 5 | Item 8 should be Arguable: no record states that staff recommended approval | 8 | Partly holds | Note-only (preferred); substantive only as sensitivity |
| 6 | Item 15 note errors: full credit, criterion 5 omitted, placeholders present | 15 | Holds (first two); partly holds (third) | Note-only |
| 7 | Items 24–25 note implies Luna wrote an insert; it did not | 24, 25 | Holds | Note-only |
| 8 | Items 3–4 fit Arguable; item 4 source cites wrong LDC subsection | 3, 4 | Partly holds; locator misstated | Substantive sensitivity; note-only |
| 9 | Item 15 fits Arguable | 15 | Holds as a sensitivity | Substantive (disclosed) |
| 10 | Items 24–25 fit Arguable, item 25 especially | 24, 25 | Partly holds (stronger for 25) | Substantive sensitivity |
| 11 | Nonparty affidavit items defensible; notes should be refocused | 14, 17–20 | Holds | Note-only |
| 12 | Penalty calls 13, 16, 22 survive | 13, 16, 22 | Holds | None or note-only |
| 13 | Calls 1, 2, 5–7, 9, 11–12, 21, 23 hold; 2019 AC-2-6 text unverifiable | 1, 2, 5–7, 9, 11, 12, 21, 23 | Holds; the unverifiability point is misunderstood | Note-only |
| 14 | Report the frozen tally, the clustering, and a sensitivity table | all | Holds | Reporting |

### 1. Item 16's environment field (holds; clerical)

**Codex's position.** Item 16 records FNC assignment 2 as Correct while items 14, 15 and 17–20 record the same assignment as Defective. Protocol §3 makes the environment verdict a property of the assignment.

**Check.** The protocol text is "each item records whether its assignment's task environment is Defective or Correct ... whether or not they touch the sampled criterion" (`README.md`, Task environment). The worksheet fields are as Codex states.

**Agreement.** All three earlier reviews say the same: both consistency passes (Opus, "Field-agreement problems"; Fable, inconsistency 1) and the item 16 stress test.

**Recommendation.** Endorsed as **clerical**, because the field is defined at the assignment level and the mismatch is mechanical. Item 16's origin stays No. Reporting effect:

- environment Defective 9 → 10 and Correct 16 → 15;
- rubric × environment, Defective row, 9 | 12 → 10 | 11;
- no change to the estimate, the objective-error count, origin, or "2 of 9 assignments".

Note the change in the worksheet, as Procedure step 4 requires.

### 2. Item 23's origin (holds; substantive)

**Codex's position.** The supplied *Facts.pdf* (PDF p. 7) says Nelson "opened fire as the Trailblazer approached". The criterion is wrong because it imports the real case's uncertainty, which is the item 10 pattern John coded origin No. The worksheet's explanation that the Facts "differ from the real record" is unverified.

**Check.** I confirmed the Facts passage (`tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-2/Facts.pdf.md`, lines 161–62, citing "TT-III 561-65, 777-80, 724-25"). I also extracted the real opinion, [*United States v. Mallory*, 104 F.4th 15 (8th Cir. 2024)](https://ecf.ca8.uscourts.gov/opndir/24/06/222777P.pdf):

- slip op. p. 2: "There was an exchange of gunfire once Mallory's SUV passed Nelson's car, though it is unclear who shot first";
- slip op. p. 4: "the shell casings and bullet fragments discovered near the intersection and the bullet holes throughout Mallory's SUV are consistent with someone else shooting before Patton did".

Codex's citation is accurate. The supplied Facts read as a party's statement with transcript cites. The Eighth Circuit's sentence characterizes disputed evidence and does not show that the trial record was altered. John's environment explanation compares the Facts with the court's characterization, not with the record. The protocol's fictional-record rule (Not defective, item (e)) points the same way.

**Agreement.** Both consistency passes and the item 23 stress test.

**Recommendation.** Endorsed as a **substantive field change**, reported as a disclosed post-tally reviewer disagreement. Origin Yes 9 → 8; nothing else in the headline moves. Separately, item 23's environment explanation should name the supplement-instruction ground recorded on items 24–25 if that verdict stands (**note-only**).

### 3. The VICAR assignment 2 environment verdict (partly holds)

**Codex's position.** The supplement-scope ambiguity on items 24–25 is neither an objective record error nor a direction to put improper work before a court. Codex therefore prefers Environment Correct for items 23–25, with origin No on all three. Alone, that gives environment 9 → 6, assignments 2 → 1 of 9, and origin 9 → 6. With finding 1, environment is 7.

**Check: the environment verdict.** On the verdict, Codex is right about the protocol's text. The two prongs are "objective errors in the supplied record, or task materials that direct work product a competent litigator should not put before a court". The upstream preamble says "Write the final complete legal deliverable for this assignment to `response2.md`. The verifier reads only that file" (`upstream-instruction.md`). The assignment says "Please supplement your brief" (`instruction.md`). That is a tension, but not an objective error. Fable (inconsistency 3) and Opus (inconsistency 5) reached the same reading, though both preferred disclosure to recoding.

**Check: origin on items 24–25.** This half is weaker. The origin field is defined more broadly, as "an error in the supplied task materials rather than in the criterion alone", and the instruction is part of the task materials. Fable calls origin Yes "defensible on the origin wording". The item 24 stress test recommends No. Both readings are reasonable.

**Recommendation.** I endorse the environment point as **reporting**. The environment table's caption should say that VICAR assignment 2's Defective verdict rests on an instruction/verifier mismatch, which goes beyond the protocol's two prongs. It can add a sensitivity line with environment 7 (with finding 1) in 1 of 9 assignments. Recoding origin on 24–25 is a closer **substantive** call, and I would not press it. The estimate is unaffected either way.

### 4. Item 10's basis (holds); the wording correction (partly holds)

**Codex's position.** Keep Defective, but the basis is professional judgment, not unambiguous objective error. *Douglas* sets no invariable separate burden to prove comparability and "Not all of these factors will be pertinent in every case". The prompt stipulates that "reasonable minds can disagree" about the comparators. John's note concedes the rubric is "perhaps narrowly correct". Codex also says the phrase "handled in the same way" misdescribes the dispute.

**Check: the basis.** The concession is in the note (worksheet item 10). The protocol reserves the objective basis for where "the record, the law, the cited authority, or arithmetic contradicts the rubric". A concession that the proposition is narrowly correct is hard to square with that label.

**Agreement.** The Opus consistency pass and the item 10 stress test agree. Fable offers an alternative: rewrite the note to lead with the *Douglas* text ("the agency establishes the facts on which that decision rests"; the penalty is "properly within its burden of persuasion"; printed pp. 333–34) together with Final Notice ¶ 19's reliance on the comparators. On that footing the objective label could stand. That alternative is real, and Codex does not engage it.

**Check: the wording.** The comparator memo says all four comparators "resulted in termination" (`comparator_discipline_cases.pdf` ¶ 1). The Award faults the showing of similar situation (¶ 7: "the Department did not prove that the comparator officers were similarly situated"). John's phrase, "If MPD cannot prove to the arbitrator that comparable cases were handled in the same way (as the Final Notice asserts)", can be read as making that point. Saying "similarly situated" would be clearer.

**Recommendation.** Endorse a disclosed **substantive** basis sensitivity: objective errors 7 → 6 of 25, estimated 18 → 15 of 63, secondary lower bound 11 → 9; the Defective count is unchanged. Fable's note-only route is the alternative if John keeps the label. The wording fix is **note-only**.

### 5. Item 8's "recommending approval" predicate (partly holds)

**Codex's position.** The criterion requires stating that "the staff report recommending approval is competent substantial evidence". No supplied passage says which way staff recommended. Codex rates the item Arguable, which would move Not defective 4 → 3 and AI reasoning Wrong 4 → 3, but no Defective figure.

**Check.** Codex is factually right. I searched the assignment's attachments for every "staff" reference. The Resolution recites only that the Board considered "the recommendations of the staff, the Hearing Examiner" and attributes "recommended APPROVAL" to the Hearing Examiner (`1774361815-resolution.docx.md`, recitals). The Petition quotes the 2023 Staff Report (SR23 pp. 3–4) without stating its recommendation (`1774361815-petition.docx.md`, around lines 323–33).

The record does support the inference strongly:

- The quoted Staff Report itself endorses the site ("County staff reviewing siting options, ultimately selecting this location after extensive due diligence").
- The applicant's planner refers to "the Staff conditions" (Petition, around line 383).
- The Board approved after considering staff's recommendations.
- This is an open-universe assignment written from the County's side, whose counsel would have the staff report.

A quick web search did not locate the DCI2023-00011 staff report, so I cannot confirm its recommendation. That point is **unverifiable** from here.

**The consistency question.** There is a real tension Codex does not frame. In items 14–20, John faults a criterion that rewards asserting record support that is not shown. Here the asserted fact is not stated either. The difference John draws in item 14 still holds: the report demonstrably exists, its favorable orientation is evident, and its author's recommendation is a matter of public record. The unsigned affidavits are different on all three counts.

**Agreement.** The item 8 stress test raised this as the strongest objection and rejected it; the consistency passes accepted the call.

**Recommendation.** **Note-only** (preferred): cite the SR23 passage and the "Staff conditions" reference, and acknowledge that the recommendation is inferred. Show Arguable only as a sensitivity line; it does not move the estimate.

### 6. Item 15 note corrections (two hold; one partly holds)

**Codex's position.** The note says Opus was "partially rewarded" on criterion 11, but the saved votes give full credit. Sonnet also rejected criterion 5 on the assignment-label ground. Opus's affidavit does contain placeholders.

**Check.** From `model-runs/lrb-forum-non-conveniens-response-assignment-2/opus55-low/reward-details.json`:

- Criterion 11's contribution is 5.0 of 5 on a 2–1 vote, with Sonnet dissenting: "The document contains no reference to an 'Assignment #2' or any assignment numbering scheme."
- Sonnet's criterion 5 vote is also a label dissent ("contains no section labeled 'Assignment #2'"), so the note's list (criteria 4, 11, 22) and the label scan omit 5. The item 15 stress test found the same.

On placeholders, Codex is only partly right. Sara Davis's affidavit (`response.md`, Exhibit 1) has blanks for the street address, city, signature and date. Its substantive paragraphs, however, assert unflagged facts found nowhere in the record (¶ 7, "I had not consulted a lawyer"; ¶ 9, the expenses). The physician form has "[Name]" and "[specialty]" blanks, yet the brief says "Each affidavit is separately signed" (line 376). John's concern, that the brief presents unexecuted forms as sworn, is accurate. Only "without placeholders" overstates.

**Recommendation.** **Note-only.**

### 7. Items 24–25 and Luna's response (holds)

**Codex's position.** Luna's assignment 2 answer carries its assignment 1 argument forward and adds *Kuhse*; it is not an insert-only supplement.

**Check.** Luna's assignment 2 response (1,501 words) opens with its assignment 1 brief (1,090 words) nearly verbatim, under a "Supplemental response" heading, and then adds a *Kuhse* section. John's note describes it as "a shorter 'Supplemental response'". So neither saved run demonstrates the insert-only misgrade; the defect rests on a hypothetical competent response.

**Agreement.** The item 25 stress test found the same.

**Recommendation.** **Note-only.**

### 8. Items 3–4 (partly holds; locator misstated)

**Codex's position.** Both items fit Arguable. Preserving the 30-day second-tier route is a reasonable choice that the real County made, and John's own note calls it "really a judgment call".

**Check.** This is a professional-judgment disagreement, not an error of record or law. The protocol rule cuts both ways: "Requiring one permissible option is not by itself a defect; rejecting a correct one is." Codex adds nothing new beyond the consistency passes (Opus inconsistency 3; Fable's Arguable boundary). The per-item stress tests for items 3 and 4 support John's Defective call and recommend note-only changes.

**The locator.** Codex's point that item 4's source cites the wrong LDC subsection holds: `citation-check/problems.md` has a row for criterion #23 (`states_in_the_first_assignment_that_the_county_should_remand_the`), "LDC 34-83(a)(4)a.1.b supports Board remand ...; (a)(6) is the six-month hearing/withdrawal provision". But Codex cites line 12, which is the row for a different criterion (#16, `..._could_remand_the`). The item 4 row is line 21.

**Recommendation.** A disclosed **substantive sensitivity** (Defective 21 → 19, estimate 48, lower bound 39). The source-pin point is **note-only**.

### 9. Item 15 as Arguable (holds as a sensitivity)

**Codex's position.** A client affidavit on residence is ordinary practice, and the motion puts residence in issue (`Defendants Motion to Transfer.pdf` ¶ 9). But no executed affidavit exists, and the closed-universe rule prevents a Not defective call.

**Check.** The record supports both halves. John's note itself calls this "a closer call because the affiant is the client". This is the item on which the most reviewers converge: the item 15 stress test (Arguable), Fable ("weakest of the six"), Opus ("Arguable boundary"), and now Codex.

**Recommendation.** A disclosed **substantive sensitivity**: Defective 20, estimate 50, lower bound 42; professional judgment 14 → 13; origin 9 → 8. The environment verdict stays Defective.

### 10. Items 24–25 as Arguable (partly holds; stronger for item 25)

**Codex's position.** The "final complete legal deliverable" preamble supports reading the task as a request for a full brief. For item 25, *Kuhse* itself makes the drive-away point relevant to the new analysis.

**Check.** *Kuhse* (`Kuhse.pdf`, PDF p. 5, line 170) lists "An alternative course of action was available to the ..." as an element of the justification instruction. Opus's assignment 2 response applies the alternative-course point (`response.md`, lines 100 and 132). Luna omitted the drive-away point in both assignments (a text search of both Luna responses finds none), so its 0/3 does not show the insert penalty. For item 24, the stationary-car fact is less tied to *Kuhse*, and John's call is stronger there, as Codex concedes.

**Agreement.** The item 25 stress test recommends Arguable. The item 24 stress test keeps Defective. Both consistency passes treat the pair as boundary items.

**Recommendation.** A **substantive sensitivity**: both items give 19 / 48 / 39; item 25 alone gives 20 / 50 / 42.

### 11. Nonparty affidavit items 14 and 17–20 (holds)

**Codex's position.** The calls are defensible. The notes should rest on the criterion's demand to say the brief "is supported by" an affidavit, and on Opus's claim that blank forms were "separately signed". They should not rest on the claim that the prompt never contemplated drafting.

**Check.** I verified the Opus brief at line 174 ("Plaintiff submits sworn affidavits from five named Cook County treating physicians") and lines 376–411 (one "[Name], M.D." form, described as "separately signed"). Codex's 16 / 40 / 32 sensitivity for moving the five items is arithmetically correct, and it rightly does not recommend that change.

**Agreement.** This matches the item 17–19 stress tests and the Opus consistency pass (inconsistency 4: rewrite the environment explanation around the "include all affidavits" instruction).

**Recommendation.** **Note-only.**

### 12. Penalty calls 13, 16 and 22 (holds)

**Check.** Item 13 holds because the assignment 1 prompt requires assessing each of the motion's arguments ("for each argument it makes, note what's strong about it, what's weak"), so a mention-based −30 penalty reaches required content. Codex here disagrees with the item 13 stress test (Arguable) and agrees with the Opus consistency pass. I find the prompt-requirement point the stronger one. Codex's item 16 and item 22 evidence matches the worksheet.

**Recommendation.** No field change. Arguable for item 22 is a fair low-impact sensitivity, **reporting** only.

### 13. Calls found sound, and the AC-2-6 point (holds, with one misunderstanding)

**Check.** I agree with Codex on items 2, 5, 7, 9, 11, 12, 21 and 23, including its note-only refinements: item 11 should rest on the record-anchoring instruction, not the training-signal rationale; item 21 should lead with § 702.11's enumerated list.

**The misunderstanding.** On items 1 and 6, Codex says it "could not verify the historical 2019 text", citing the citation-check's own limit. But John's note cites the archived [AC-2-6 as amended through 11/17/15](https://web.archive.org/web/20170727083947/http://www.leegov.com/bocc/Administrative%20Codes/AC-2-6.pdf). I retrieved it. Its amendment list ends "6/21/11, 6/12/2012, 11/17/15". § 4.1 is headed "Applications or Appeals Remanded by the Board to the Hearing Examiner". § 4.1B(1) reads "If the six month deadline is not met because of action or inaction of the Applicant/Appellant, the application/appeal will be considered withdrawn." The point Codex calls unverifiable is verifiable, and the item 1 stress test had verified it.

**Recommendation.** For items 1 and 6, adopt the item 1 and 6 stress tests' note-only suggestion to lead with § 4.1's Board-remand limitation.

### 14. Reporting (holds)

**Check.** I recomputed every figure Codex reports with the exact one-sided hypergeometric bound:

| Defective / 25 | Estimate / 63 | Lower bound / 63 |
|---:|---:|---:|
| 21 | 53 | 45 |
| 20 | 50 | 42 |
| 19 | 48 | 39 |
| 16 | 40 | 32 |
| 7 (objective) | 18 | 11 |
| 6 (objective) | 15 | 9 |

Codex's statement about what the bound does and does not cover matches the protocol's limits. So does its point that clustered criteria are units rather than independent mistakes.

**Recommendation.** **Reporting:** publish the frozen tally as John's result; disclose the item 16 clerical fix; add one compact sensitivity table. The Opus and Fable passes give fuller versions, and Fable's floor row matches the reconciliation's retained "problematic" set (8 / 20 / 13).

## What Codex misunderstood or misstated

- **Items 1 and 6.** It called the 2019-era AC-2-6 text unverifiable, overlooking the archived 11/17/15 text cited in John's note. That text is the version in force in 2019–20, and its § 4.1 and § 4.1B(1) match the 8/2/22 text.
- **Item 4.** It cited the citation-check row for criterion #16 (`problems.md` line 12) instead of the row for item 4's criterion #23 (line 21). The substance is right.
- **Item 15.** "Its answer does contain placeholders" is true only of the address, signature and date blanks. The substantive sworn statements are unflagged.
- **No error of principle.** I found no misreading of the penalty direction, the research universe, the fictional-record rule, or the rubric-versus-environment distinction. Codex's environment analysis tracks the protocol's text more literally than John's coding does.

## Points Codex left on the table

- **The DCCA record has apparent unplanted errors that bear on the environment field for items 9–11.** The item 9 stress test raised this; Codex did not address it. I verified two inconsistencies.
  - Comparator memo ¶ 4 places Comparator C's shooting "in the District" but says "The Commonwealth declined prosecution". Prosecutions in D.C. are not brought by a Commonwealth; the Final Notice's reference to the Commonwealth's Attorney for Fairfax County concerns Braddock's own incident.
  - Award ¶ 7 says "Two of the four comparators involved on-duty conduct", but the memo shows three on duty (Comparators A, B and D, ¶¶ 2, 3, 5).

  A search of the rubrics for DCCA assignments 1–5 (`input.json`) found no criterion that targets either point. The only related criterion (assignment 2, criterion 10) rewards noting that on-duty status was one of the arbitrator's grounds, not the miscount. So both appear unplanted. Under protocol §3, these are "objective errors in the supplied record ... whether or not they touch the sampled criterion". The attachments accumulate, so this would make DCCA assignments 1–3 (items 9, 10 and 11) environment Defective.

  This is a **substantive** change to the environment table only: Defective +3, and assignments with a Defective environment 2 → 3 of 9 (or 2 of 9 if the VICAR assignment 2 verdict also moves). It is not a rubric change; item 9's Defective call does not depend on it. I hold this with medium confidence. It turns on whether the protocol's environment verdict is meant to capture minor unplanted inconsistencies, and the protocol text says it is.
- **A second ground for items 18–20.** The Opus consistency pass notes that each criterion's "as required under *Langenhorst*" misstates the case, which puts the inconvenience showing on the defendant (219 Ill. 2d at 444). The matter's citation check also flags this. Codex did not mention it. **Note-only.**
- **Fable's alternative for item 10.** Codex did not engage Fable's textual route for keeping the objective basis on item 10 (see finding 4).

## Recommendations endorsed, with classification and reporting implications

| Recommendation | Items | Classification | Reporting implication |
|---|---|---|---|
| Environment field to Defective | 16 | Clerical | Environment 9 → 10; rubric × environment Defective row 10 \| 11; note the fix in the worksheet |
| Origin Yes → No | 23 | Substantive | Disclosed sensitivity: origin 9 → 8 |
| Caption the environment table: VICAR assignment 2 rests on an instruction/verifier mismatch; optional sensitivity line | 23–25 | Reporting | Environment 7 in 1 of 9 assignments (with the item 16 fix) |
| Basis to Professional judgment, or Fable's note-only rewrite | 10 | Substantive (or note-only) | Objective 7 → 6; estimate 18 → 15; secondary bound 11 → 9 |
| Arguable sensitivities: items 3–4, 15, 24–25 (with 25 the stronger) | 3, 4, 15, 24, 25 | Substantive (disclosed only) | Combined Defective 16; estimate 40; bound 32. Singly as given in findings 8–10 |
| Cite the inference for staff's recommendation; Arguable only as a sensitivity | 8 | Note-only | None to the Defective figures |
| Note corrections: full credit and criterion 5 (item 15); Luna's answer is a full brief plus *Kuhse* (items 24–25); "similarly situated" (item 10); placeholders (items 14–15); § 4.1 Board-remand limitation (items 1, 6); § 702.11 first (item 21); record-anchoring rationale (item 11); LDC pin (item 4); *Langenhorst* ground (items 18–20) | various | Note-only | None |
| DCCA environment, for the unplanted record errors | 9–11 | Substantive (environment table only) | Environment +3; assignments with a Defective environment 2 → 3 of 9 |
| Publish the frozen 21/25, 53, 45 with one sensitivity table and a count of underlying mistakes (about 12–13 for the 21 Defective criteria) | all | Reporting | Headline unchanged |

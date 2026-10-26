# Combined assessment of the stress tests

This combines the 25 per-item stress tests, the two consistency passes, and the independent Codex review with its assessment. It is a set of proposed revisions and disagreements for John to consider. It does not change the recorded worksheet fields or notes. The tally was already run on the completed worksheet ([`tally-at-review-start.txt`](tally-at-review-start.txt)): 21 Defective, 0 Arguable, 4 Not defective; estimate 53 of 63, one-sided 95% lower bound 45; objective errors 7 (bound 11); environment Defective on 9 items. Under the protocol, verdicts change after the tally only to fix clerical errors, so every recommendation below is classified.

## What ran, and what it proves

- **Per-item:** 25 Claude Opus 5.5 agents at high effort, one per sampled criterion ([prompt](prompts/01-per-item-stress-test.md); reports in [`items/`](items/)).
- **Consistency:** Claude Opus 5.5 and Claude Fable 5.1 at high effort, run independently and in parallel with the per-item agents ([prompt](prompts/02-consistency-pass.md); [Opus](consistency/opus.md), [Fable](consistency/fable.md)).
- **Codex:** an Opus 5.5 orchestrator wrote a [methodology summary](codex/methodology-summary.md) and the [Codex prompt](codex/codex-prompt.md), which carries John's instruction verbatim. It ran `codex exec` with **gpt-6-sol at high reasoning effort**, read-only with live web search (codex-cli 0.164.0; exit 0; about 7 minutes; [run record](codex/codex-run.md)). It then [assessed](codex/assessment.md) the [Codex review](codex/codex-review.md) against the record.
- **Orchestration:** [`prompts/workflow.js`](prompts/workflow.js). All 28 agents completed.

All of these are AI reviews. Agreement among the Claude agents is not independent verification. Codex is a different model family, but it was not blind: it read the earlier reviews, as the prompt invited, and its local memory held notes from earlier sessions in this repository (see the [run record](codex/codex-run.md)). I checked the points below that drive my recommendations against the primary sources myself; the agents' other legal-research claims are labeled where I did not.

## Bottom line

The headline result survives. No reviewer would move any of the eight items the reconciliation retained as problematic. Every reviewer found the objective-error calls on items 1, 5, 6, 9 and 21 sound, as well as the four Not defective calls (Codex's item 8 dissent aside). Their criticisms fall into three groups:

1. **One genuine clerical fix:** item 16's environment field.
2. **Coding inconsistencies in the secondary fields:** item 23's environment origin, item 10's objective-error basis, and the environment field generally. These do not touch the estimate.
3. **The empty Arguable band.** Every cross-item reviewer flagged it. Your notes use Arguable language ("really a judgment call," "a closer call," "perhaps narrowly correct") on items recorded Defective. This is the finding most likely to be raised against the review, and it should be answered with a disclosed sensitivity table rather than recoding.

## Findings by classification

### A. Clerical (permitted after the tally, with a note in the worksheet)

**Item 16, Environment: Correct → Defective.** All reviewers agree. Protocol §3 makes the environment verdict a property of the assignment ("whether its assignment's task environment is Defective or Correct ... whether or not they touch the sampled criterion"). Items 14, 15 and 17–20 record forum non conveniens assignment 2 as Defective, so item 16 has to match. Origin stays No. Effect: environment Defective 9 → 10; rubric-by-environment cells Defective|Defective 9 → 10 and Defective|Correct 12 → 11. No effect on the estimate. This is the only change I would make in the worksheet itself, noted as a clerical correction.

### B. Substantive field disagreements (report alongside the frozen fields; do not edit)

1. **Item 23, origin Yes → No.** Unanimous: both consistency passes, Codex, the assessor, and the item-23 stress test. Your note says the rubric "would be correct for the real-world case [but] is incorrectly applied to this task environment." That describes a rubric error, which item 10 codes origin No for the same pattern. The supplied Facts.pdf (PDF p. 7) is internally consistent, and the same file is coded as a Correct environment for VICAR assignment 1 (items 21–22). The environment explanation, "differs from the real record," is also unverified. The real trial record is not public, and *Mallory*, slip op. at 4, describes physical evidence "consistent with someone else shooting before Patton did" (agent-verified; I did not re-read the opinion). That fits the Facts. Effect: origin Yes 9 → 8. The Defective verdict and the objective-error basis stand.
2. **Item 10, basis Unambiguous objective error → Professional judgment.** The Opus consistency pass, Codex, the assessor and the item-10 stress test recommend this. Fable would keep the label but rewrite the note to rest on *Douglas* printed pp. 333–34. Your own note concedes the criterion is "perhaps narrowly correct as a general proposition of law." The assignment 2 stipulation (a) says "reasonable minds can disagree as to how comparable the four comparator cases are." And the 2026 *MPD v. PERB* opinion you cite says "MPD is correct about its burden under Douglas" (slip op. at 9, agent-verified). A defender would quote all three back. Effect: objective errors 7 → 6, objective lower bound 11 → 9. The headline is unchanged. The item-10 stress test would go further, to Arguable (see C).
3. **VICAR assignment 2 environment (items 23–25).** With item 23's "real record" ground unverified, the remaining ground is the ambiguity in items 24–25 over whether `response2.md` must be a complete brief. That is neither an objective record error nor a direction to put improper work before a court, the protocol's two grounds. Codex would recode the environment to Correct. Both consistency passes and the assessor prefer keeping Defective with a caption disclosing the broader reading. I agree with the caption: an instruction that conflicts with the verifier's grading arguably belongs to the "task materials," but the reader should be told.
4. **Environment errors you did not record, which I verified:**
   - *DCCA (items 9–11).* Award ¶ 7 says "Two of the four comparators involved on-duty conduct," but the comparator memo shows three on duty: Guzman, Sadler and Voss (memo ¶¶ 2, 3, 5; Pietrzak alone was off duty, ¶ 4). Memo ¶ 4 says "The Commonwealth declined prosecution" of an off-duty shooting "in the District." I searched all five DCCA rubrics and found no criterion rewarding either point, so neither is a planted error. Under the protocol's definition, both make the DCCA environments Defective. The miscount is the material one, because the arbitrator's comparability reasoning rests on it.
   - *Forum non conveniens (items 13–20).* The partner's email says Baby Davis was transferred to "Lurie's Children's Hospital" and "almost passed away on September 16, 2024." The Complaint says he was transferred to and died at "Cook County Hospital" (¶¶ 27, 29). The defendants' filed affidavits also carry unfilled "[Records Custodian]" and "[street address]" placeholders (motion, Ex. B and Ex. A ¶¶ 2–4). These give forum assignment 2 a firmer, objective environment ground than the one recorded. They would also make forum assignment 1 (item 13, recorded Correct) Defective.
   - *Effect if adopted:* environment table only. With the item 16 fix, environment Defective would rise from 10 to 14 items, in 5 rather than 2 of 9 sampled assignments, or 11 items in 4 assignments if VICAR assignment 2 moves to Correct. Whether a "Commonwealth" slip is worth counting is your call. The protocol's definition does not exclude small objective errors, so if you leave them out, say so.

### C. Verdict sensitivities: the Arguable boundary

No reviewer recommends silently recoding verdicts. All three cross-item reviewers recommend a disclosed sensitivity table. Fable's diagnosis is the clearest. You apply one consistent test: Defective whenever you can describe a competent response that the criterion, read literally, would misgrade. That reading is legitimate, but it leaves Arguable empty by construction. It gives no work to the protocol's "affects only unusual responses" clause or to "borderline or low-impact concerns are Arguable." The Opus pass adds that the protocol's two rules overlap ("requiring one permissible option is not by itself a defect"; "rejecting a correct one is"), and you resolve the overlap toward Defective.

Where the reviewers would move items, and where they split:

| Item(s) | Per-item stress test | Consistency passes | Codex (and assessor) | My view |
|---|---|---|---|---|
| 15 (Sara Davis affidavit) | Arguable | sensitivity | Arguable (holds) | **Arguable is the better fit.** A client residence affidavit drafted for her signature is ordinary practice, satisfies the criterion, and is what assignment 1 criteria 10–11 told the solver to recommend. Your note calls it "a closer call." |
| 25 (could have driven away) | Arguable | sensitivity | Arguable (partly holds; stronger than 24) | **Arguable is the better fit.** Both native solvers wrote complete briefs, so the insert-only failure is hypothetical. *Kuhse*'s own instruction 13(2), "An alternative course of action was available" (Kuhse.pdf PDF p. 5), lets a Kuhse-only insert reach the point. |
| 24 (car already stopped) | Defective, near the line | sensitivity | Arguable (partly holds) | Close; defensible either way. |
| 3–4 (appeal; remand while appeal pending) | Defective holds | sensitivity | Arguable (partly holds) | **Hardest call to defend as written.** Your note calls it "really a judgment call," which is the protocol's own Not defective language, and the real County did both. The stress tests' best defense is that a +20 reward rejects a remand-only memo, an approach careful counsel would adopt. It needs answers to the irrevocable 30-day deadline and cheap protective filing, the bias finding attaching to the same Board, and the FAA holding constraining remand. |
| 10 (no uploaded authority requires proof of comparability) | Arguable | basis → PJ | basis → PJ | Keep Defective on a Professional-judgment basis (see B.2). |
| 13 (penalty: "Mentions ... Cook County lacks interest") | Arguable | Opus: Defective; Fable: sensitivity | Defective (holds) | Split. The motion never says "lacks interest," and 0 of 6 judge votes fired. The twin criterion 25 did fire 6 of 6 on the same "Mentions" wording, and the prompt requires assessing every defense argument. Defensible as Defective. |
| 14, 17–20 (nonparty physician affidavits) | 14 and 20: Arguable; 17–19: Defective | Fable: largest lever | Defensible as Defective; notes need refocusing | See D.1. That identically structured criteria drew opposite stress-test verdicts is itself evidence that this family sits in the reasonable-disagreement zone. |
| 22 (−5 "Mentions" penalty) | Defective holds | Fable: low-impact sensitivity | Defective holds | Keep. The misgrade actually happened (Opus's accurate drafting note was penalized 2/3). |
| 8 (staff report, Not defective) | Not defective holds | holds | Arguable (partly holds) | Keep Not defective. No supplied passage says staff recommended *approval*, but the universe is open, the County is the applicant, and the Petition quotes "Staff conditions." Strengthen the note. |

Sensitivity ladder (my recomputation of the protocol's exact hypergeometric bound; it matches every reviewer's figure):

| Reading | Defective / 25 | Estimate / 63 | 95% lower bound |
|---|---:|---:|---:|
| As tallied | 21 | 53 | 45 |
| Item 15 → Arguable (broadest agreement) | 20 | 50 | 42 |
| plus item 25 | 19 | 48 | 39 |
| plus items 3–4 | 17 | 43 | 34 |
| plus item 10 | 16 | 40 | 32 |
| plus items 14, 17–20 (the whole affidavit family) | 11 | 28 | 20 |
| Fable's floor: only the reconciliation's eight retained "problematic" items | 8 | 20 | 13 |

Objective-error secondary figure: 7 (bound 11) as tallied; 6 (bound 9) with item 10's basis recoded.

### D. Note-only corrections and stronger arguments (no tally effect)

1. **Affidavit family (14, 15, 17–20): the most important note revision.** The notes say "the prompt does not instruct the model to create one" and that the record "shows [the affidavits] have not been signed." Both are vulnerable. I confirmed that assignment 1's rubric rewards recommending exactly these affidavits: criterion 13, +1, "obtain affidavits from the 5 Cook County Hospital Doctors," and +10/+15 for Sara Davis's residence and inconvenience affidavits. Assignment 2 then says "Please include all affidavits and information you referenced from Assignment #1" and lists the doctors' names. The only plaintiff-side affidavits assignment 1 "referenced" are the ones the memo was supposed to recommend, so "include" most naturally means *draft them*. The record is silent on execution; it does not show that anything went unsigned. Your stronger ground, which the item 17–19 stress tests and Codex develop, is this. The criterion pays for the representation that "the response *is supported by* the affidavit," and it cannot distinguish a draft clearly marked for execution from a brief that falsely says the forms were "separately signed." It paid Opus 3/3 for the latter. That makes the criterion pass work that is wrong on the very point it covers, which is one of the protocol's two Defective prongs, without denying that drafting proposed affidavits was requested. Further additions:
   - Origin Yes then rests on the conflict between "include all affidavits" and "If a document is not uploaded, it does not exist," not on the absence of an instruction.
   - Use with care: Luna, which you hold up as the better approach, scored 0 partly because it wrongly said the record does not show the physicians' willingness to testify.
   - Items 18–20 have a second ground: "as required under Langenhorst" misstates the case, which places the inconvenience showing on the defendant (219 Ill. 2d at 444; citation check FNC-0049, mischaracterized).
   - The appellate-record distinction from items 7–8 is strong: those briefs cite evidence already in the record below, while these assert new sworn testimony from nonparties.
2. **Items 1 and 6: lead with the objective ground the notes leave out.** AC-2-6 § 4.1 governs only applications "remanded to the Hearing Examiner by the Board." The 2019 remand ran from the Hearing Examiner to staff, on a joint request (Petition p. 18). The supplied Order itself rests on DCI2018-10023 having "remained an active case" (Order pp. 3–4). The applicant-fault point is weaker than the notes suggest: the applicant was Lee County Utilities, which let the case sit for years. Treat the real parties' positions as context, not "ground-truth evidence." The Codex assessor retrieved the archived 11/17/15 text and confirmed it matches, which answers Codex's claim that the 2019 text was unverifiable.
3. **Item 2.** "Municipality" should be "county" (three times). *Parkway Towers* discharged a conflict-certiorari writ as improvidently granted; it did not decline to hear an appeal in an exercise of discretion. "Essentially says the opposite" overstates, since the disposition did leave construction undisturbed to avoid "needless expense." Stronger evidence: the rubric's own law-review source (Smith, 28 Fla. L. Rev. 800, PDF p. 17) reads the case as subjecting a county to its own zoning, and the LCU Project Detail shows only weeks of site clearing.
4. **Item 3.** The County's Sixth DCA petition concedes mootness is *arguable* ("might arguably render ... technically moot"); it does not "essentially acknowledge" likely mootness. Source the February 2026 re-approval or drop it. Add the stress test's point that the rubric's "reversible errors" premise misstates the narrow second-tier standard (*Haines City*/*Heggs*; agent-sourced, not checked by me).
5. **Item 4.** "Hearing officer" should be "Hearing Examiner." Replace "incorrect" with the protocol's rejects-a-permissible-approach language, and add a source locator.
6. **Item 5.** Add the statute's limiter, "because of a deficiency in the approval standards." Answer the reading that the criterion means a separate downstream development order.
7. **Item 7.** The Petition does quote the County's expert witnesses with Tr1 pin cites, so the note concedes too much. Engineer Erik Howard (Tr1 pp. 36, 40–41, 241) is the better locator than planner Crespo.
8. **Item 10.** "Handled in the same way" is wrong: all four comparators were terminated, and the dispute is whether they were *similarly situated*. Label the pins as M.S.P.B. pages. The rubric does not "import" the real case's rule; it penalizes that rule (criterion 5, −18).
9. **Item 11.** Restate the reasoning in protocol terms, not "desirable training signal." The prompt's direction to anchor in PERB's findings makes noting the 40/45-day discrepancy a demanding but defensible standard.
10. **Item 12.** Sol called it Arguable and did not say the affidavit "clearly" shows anything. Langenhorst's affidavits were "not inconvenient" statements rather than comparative ones, so "expressly teases out" slightly overstates.
11. **Item 13.** The note says the misspecification "seems to impact the grading," but its own native-run line reports 0 of 6 votes fired. Lead with criterion 25's 6-of-6 misfire on the same wording and with the prompt's requirement to assess each argument.
12. **Item 15.** Opus received the full 5 points by a 2–1 vote, not partial credit. Opus's Exhibit 1 does have address, signature and date blanks; the problem is that the brief calls it sworn. Sonnet's label-only dissent also hit criterion 5.
13. **Item 16.** Luna gave no civil-category rates and conceded "some support." Only Opus "explained why" civil data mattered.
14. **Item 21.** Lead with the supplied text: § 702.11 does not list conspiracy, and the rubric's own justification for criteria 28–29 rejects the parallel theory as circular. Frame the independence principle as the better reading, supported by *Heemstra* (Iowa's merger rule) and *Martinez* (Fla.), since no Iowa § 704.6(1) case was found. Cite *Martinez* from a court source rather than a blog. The burglar example fits Iowa poorly, because only first-degree burglary is a forcible felony; use an armed robber.
15. **Item 22.** "Prior conviction" is inaccurate: the Count XX petition is dated November 18, 2020, after the May 10 shooting, and the record shows plea petitions, not a judgment. Drop the "who the defendant is" rationale and rest on the misfire.
16. **Items 24–25.** Luna's answer reproduces its whole assignment 1 brief and then adds *Kuhse* sections (I confirmed: 1,501 words, opening with its 1,090-word assignment 1 brief nearly verbatim). Don't describe it as a shorter supplement. "Token inefficiency" mislabels the issue, which is unrequested scope (basis (c)). The "related items" lines refer to themselves.

## Where the reviewers disagree

- **Item 13:** the stress test says Arguable; Codex, the assessor and the Opus pass say Defective.
- **Items 3–4:** the stress tests defend Defective; Codex would mark both Arguable.
- **The affidavit family:** the five stress tests split 2–3 on materially identical criteria. Fable treats the family as the single largest lever; Codex and the assessor call the nonparty items defensible.
- **Item 8:** only Codex dissents, toward Arguable. The assessor rates that dissent partly sound and supports a note fix only.
- **VICAR assignment 2 environment:** Codex would recode; the others would disclose.
- **Item 10:** recode the basis (Opus, Codex) versus keep the label and rewrite the note (Fable).

## My assessment

The strongest findings, in order of importance to the conclusions:

1. **The empty Arguable band needs an explanation in the write-up.** Your test is coherent and consistently applied, and the result is defensible. But a reader will see 21/0/4 next to notes that say "judgment call" and "closer call," and micro1 would make that its first point. Publish the frozen 21/25 (53, lower bound 45) as your considered result, state your operative test explicitly, and add the sensitivity ladder. Even at the reconciliation's floor (8/25), at least 13 of the 63 flagged criteria are defective.
2. **The affidavit-family notes must confront "include all affidavits ... you referenced from Assignment #1."** As written, they deny an instruction that the assignment 1 rubric makes plain. The Defective call can survive on the "passes wrong work on the point it covers" ground, but not on the current framing.
3. **Item 10's "unambiguous" label is the weakest objective-error call,** and the authority you cite gives a defender its best quote. Moving it to Professional judgment costs one objective error and two points of the secondary bound. That is cheap insurance.
4. **The environment field is applied less uniformly than the rubric fields.** That covers item 16 (clerical), item 23's origin, the VICAR assignment 2 ground, and the unrecorded DCCA and forum record errors. None of it touches the estimate, but the environment table is where your rubric-versus-environment distinction is on display, so it is worth getting right.

**What still concerns me:**

- Items 3–4 are the calls I would least want to defend under cross-examination. The protocol's own Not defective example ("a judgment call where the criterion takes a reasonable side") matches your note's words, and the real County did exactly what the rubric rewards.
- Several notes lean on the real litigation (items 1, 3, 6, 10, 23). Where the real record cannot be verified (item 23), or where it cuts toward the rubric (item 10's 2026 quote; item 3, the County appealed), that reliance weakens the call. Keep the real case as context and rest the call on the supplied record and governing law.

**Stronger arguments you should use:**

- Items 1 and 6: § 4.1's Board-remand-only scope.
- Item 21: § 702.11's list, *Heemstra*, and the rubric's own "circular" rejection in criteria 28–29.
- Item 2: the rubric's own law-review source.
- The affidavit family: the criterion's inability to distinguish draft from executed, and the Langenhorst misstatement in items 18–20.
- Item 16: the twin criterion 25's justification shows the author meant to bar naming the figure at all.
- Item 25: *Kuhse*'s alternative-course instruction.

## Reporting implications

- Make the item 16 clerical fix in the worksheet, with a dated note.
- Report everything in B and C as disclosed post-tally reviewer disagreements or sensitivities, not edits.
- Note-only revisions (D) do not change recorded fields. If you revise notes after the tally, a one-line dated disclosure of that fact would keep the record clean.
- Report the 21 Defective criteria as roughly 12–13 underlying mistakes, as both consistency passes suggest. The affidavit family (6), the AC-2-6 pair (2), the appeal/remand pair (2) and the VICAR supplement pair (2) cluster. The protocol already says the count is of criteria, not independent mistakes; a short root-cause table makes that concrete.

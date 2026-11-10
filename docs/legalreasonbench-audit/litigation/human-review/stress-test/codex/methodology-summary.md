# Summary of the reviewer's stated methodology

This is a neutral summary of the methodology John Hughes (the reviewer and project author) has stated for the LegalReasonBench human review. It draws only on the protocol (`docs/legalreasonbench-audit/litigation/human-review/README.md`, cited as "Protocol") and on the notes he recorded in the 25 review blocks of `docs/legalreasonbench-audit/litigation/human-review/worksheet.md` (cited as "item N"). It does not include suggestions made by the per-item stress tests or the consistency passes. Where a principle appears only in the notes, it is described as the notes apply it, not as a rule the protocol states.

**The tally has been run.** All 25 items are complete, and the output is saved in `stress-test/tally-at-review-start.txt`: Defective 21, Arguable 0, Not defective 4, Unresolved 0; estimate 53 of 63; exact one-sided 95% hypergeometric lower bound 45 of 63. Under the protocol, verdicts may now change only to fix clerical errors, and any such change is noted in the worksheet (Protocol, Procedure step 4).

## 1. Unit and question

- **Unit.** "A distinct assignment–rubric-criterion pair, identified by assignment ID and the upstream criterion ID." It is "not an AI finding, an underlying mistake, a document, or a matter," and a criterion that repeats a point from another assignment is a separate unit (Protocol, Sample).
- **Population and draw.** The 63 criteria that either blind AI report (GPT-6 Sol or Claude Opus 5.5) labeled problematic or arguable, deduplicated; a simple random sample of 25 with seed 20261024 and no replacements (Protocol, Sample). The later reconciliation is "metadata, not eligibility."
- **Question.** "Whether the criterion, applied as written to the task as given, would misgrade a permissible competent response, not whether an AI's write-up is persuasive." The task as given "includes the current prompt and its stipulations, earlier prompts in the same matter, the accumulated attachments, and the stated research universe" (Protocol, What the reviewer decides).

## 2. Verdict definitions (Protocol §1)

- **Defective.** "Applied as written to the task as given (instructions, supplied documents, and governing law), the criterion would grade a competent response wrong on the point it covers. It would either fail a response that a careful litigator would consider correct, or pass one that is wrong," for at least one of four reasons: (a) the expected answer contradicts, or is unsupported by, the supplied record; (b) it states or depends on an incorrect legal proposition; (c) it requires something the instructions did not ask for and that a competent lawyer would not reasonably infer; (d) it conflicts with the instructions or another criterion.
- **Arguable.** "Reasonable litigators could disagree about whether the criterion would misgrade a competent response, or the problem would affect only unusual responses."
- **Not defective.** "The criterion grades correctly," including "a demanding but defensible standard; a judgment call where the criterion takes a reasonable side; a stylistic preference stated in the task; a document inconsistency that does not change what the criterion requires; and an instruction in a fictional or hypothetical record that a response can reasonably follow, even where it misstates real-world law."
- **Unresolved.** The reviewer cannot decide from the record and the available authority.
- **No severity scale.** "Materiality is part of the definition of Defective, and borderline or low-impact concerns are Arguable."

## 3. The two recurring situations (Protocol §1, decided as in the Harvey review)

- **One of several permissible approaches.** "A criterion may prefer one approach. It is Defective when it rejects an approach a careful litigator would adopt on this record. Requiring one permissible option is not by itself a defect; rejecting a correct one is."
- **Defects in the environment.** "An unplanted error in the supplied record (conflicting figures, arithmetic that does not add up, fabricated or misdescribed authority) makes a criterion Defective when it changes what a competent response can get right." A criterion can also be defective by passing wrong work. "When the record is objectively wrong but the criterion still grades correctly, the verdict is Not defective (an environment-only defect). Planted mistakes that the task asks the solver to catch are not environment defects."

## 4. Penalty criteria

"A penalty criterion is judged the same way: would imposing the penalty as written misgrade a permissible competent response?" (Protocol, What the reviewer decides). The notes apply this to five sampled penalties (items 1, 2, 13, 16, 22), all recorded Defective.

## 5. Hypothetical or fictional records

The Not defective definition covers "an instruction in a fictional or hypothetical record that a response can reasonably follow, even where it misstates real-world law" (Protocol §1). In the notes, the reviewer treats the task environment, not the real case behind it, as what the solver must follow: a rubric that carries a proposition from the real case onto task facts that were changed is defective because it "fails to take into account how this task environment was modified from the real case" (item 10), and "a rubric that would be correct for the real-world case is incorrectly applied to this task environment" (item 23).

## 6. Research universe

- **Protocol.** "In a closed-universe assignment, outside authority can show that supplied law is wrong but does not enlarge what the solver was permitted to use."
- **Open universe, as applied.** In item 1 the note says the county rule the rubric relies on "is not cited in the environment but can be found using web search (which models are allowed to use here)," and the note evaluates the rule's text.
- **Closed universe, as applied.** The notes quote the closed-universe instructions as limits on what the solver may assume: "If a document is not uploaded, it does not exist for purposes of this analysis" (item 14) and "Be sure to limit your review for the Assignment to the attached documents" (item 23). Outside authority is used to test supplied law or the rubric's legal premise (item 21 cites *Martinez v. State*, 981 So. 2d 449 (Fla. 2008), as persuasive authority on the Iowa forcible-felony bar, noting that no Iowa case was found "during a quick search").

## 7. Defect basis and environment origin (Protocol §1)

For each Defective verdict:

- **Defect basis.** "*Unambiguous objective error* (the record, the law, the cited authority, or arithmetic contradicts the rubric) or *Professional judgment*." Objective errors are reported as a separate count with their own lower bound. Recorded: objective error on items 1, 5, 6, 9, 10, 21, 23; professional judgment on 2, 3, 4, 13, 14, 15, 16, 17, 18, 19, 20, 22, 24, 25.
- **Defect arises from environment.** "*Yes* if the defect stems from an error in the supplied task materials rather than in the criterion alone; otherwise *No*." Recorded Yes on items 14, 15, 17–20, 23, 24, 25.

## 8. AI reasoning (Protocol §2)

Did a flagging model's blind report identify the actual problem? **Correct**: at least one flagging model's stated reason is why the criterion is defective or arguable. **Partly correct**: the right issue, with part of it misstated (law, record cite, or scope). **Wrong**: no model's reason holds up; "this always applies when the verdict is Not defective," and also when the reviewer finds a defect on a ground the models did not give. The reconciliation is not scored. Recorded: Correct on all 21 Defective items, Wrong on the 4 Not defective items.

## 9. Separate environment field (Protocol §3)

"Separately from the rubric verdict, each item records whether its assignment's task environment is Defective or Correct." The verdict "turns on objective errors in the supplied record, or task materials that direct work product a competent litigator should not put before a court, whether or not they touch the sampled criterion." Environment verdicts are reported in their own table against the rubric verdicts and "do not enter the estimate." Recorded Defective on items 14, 15, 17–20 (forum non conveniens assignment 2; missing affidavits) and 23–25 (VICAR assignment 2; item 23 on the supplied facts' departure from the real record, items 24–25 on the supplement instruction and re-grading). Item 16, also in forum non conveniens assignment 2, is recorded Correct.

## 10. Post-tally change rule

"After the tally, verdicts change only to fix clerical errors, and any such change is noted in the worksheet" (Protocol, Procedure step 4). The analysis plan was fixed in advance: only Defective verdicts count; Arguable, Not defective and Unresolved stay in the denominator of 25 (Protocol, Analysis).

## 11. Recurring principles in the notes

These are principles the notes apply across items. They are stated as the notes state them.

- **Penalties worded "States" or "Mentions."** A penalty that, as worded, "can reach a response rebutting or setting aside the point" misgrades competent work. The notes group items 1, 13, 16 and 22 under this heading and report that the native runs misfired on 16 and 22. In item 13 the note relies on the possibility of misgrading ("a grader could apply this penalty even to a memo that simply 'mentions' the defendants' argument and then correctly explains why it's wrong"), and reports that the penalty did not fire in either native run. In item 16: "the defendants' opening brief squarely presents the 60.5% statistic to the Court -- so any competent opposition would respond to that argument." In item 22: "A competent lawyer could also mention the defendant's prior convictions as part of the factual background."
- **Use of the real litigation behind a matter.** The notes use the real case (identified in `real-cases.json`) in three ways: as evidence about the parties' positions (item 1: the rubric "seems to be contradicted by the ground-truth evidence from the litigation"; item 6: "Neither party in the actual litigation contends"); as evidence of what real counsel did and conceded (item 3: the county's second-tier petition "essentially acknowledged that the remand was likely to moot the appeal"; item 21: neither the Eighth Circuit nor the government's certiorari opposition relied on the rubric's theory); and to show that a rubric imported a real-case proposition onto changed task facts (items 10, 23). The protocol describes `real-cases.json` as "context for the reviewer" on which "a reviewer's note may rely."
- **Strategy criteria.** Where a criterion requires one strategy, the notes ask whether careful counsel would advise another: item 2 ("Many prudent lawyers, relying on the Florida Supreme Court's guidance, might recommend addressing the zoning issue before continuing with construction"); item 3 ("very good reasons not to appeal ... that's really a judgment call — so the rubric would incorrectly effectively penalize a failure to pursue a strategy many lawyers would advise against"); item 4 (remand is right, but "while an appeal is pending" also requires an appeal).
- **Evidence referred to but not supplied, versus evidence that does not exist.** Items 7 and 8: a competent lawyer would cite expert testimony and a staff report that the record shows exist even though they are not uploaded. Item 14 distinguishes the affidavit items: "we had clear indications that the expert analysis described really existed," whereas "the environment makes clear that the affidavits do not exist and have not been signed by anyone."
- **Unexecuted affidavits and placeholders.** Item 14: "Drafting an opposition brief that cites to affidavits (without placeholders in the draft) is extremely hazardous behavior to train models on"; "The normal approach ... would be to draft placeholder citations to an affidavit that make clear the language must be adjusted to conform to the witness's final testimony"; "a nonparty is entitled to decide exactly what it is willing to affirm in writing." Item 15 applies the same reasoning to the client's affidavit and calls it "a closer call because the affiant is the client."
- **Points beyond the prompt.** Item 11 treats flagging a record discrepancy the prompt did not ask about (PERB's 40-day versus the Award's 45-day suspension) as improving an internal memo and "a desirable training signal."
- **Defendant's burden on forum non conveniens.** Item 12: under *Langenhorst*, "a defendant seeking to move on forum non conveniens grounds needs to establish that the plaintiff's chosen forum is actually inconvenient to the defendant," not merely that another forum is more convenient.
- **Sequential assignments.** Items 24 and 25: when assignment 2 asks only to "supplement your brief," re-grading five assignment 1 criteria on `response2.md` penalizes a model that reasonably writes only the new material; the note says this "appears to reward token inefficiency, and it is not what the prompt clearly requests."
- **Benchmark-wide grading issues are not per-criterion defects.** Item 15: criteria that name an assignment number the judge cannot see are "an overarching issue in the benchmark setup that can be addressed globally," and are not treated as a rubric defect.
- **Native model-run grades as evidence.** Several notes report how the native judges actually graded saved solver responses (items 1, 13, 14, 15, 16, 17–20, 22, 24, 25), including where a penalty did not fire (item 13) and where a criterion rewarded a brief citing an unsigned form as executed affidavits (items 14, 17–20).

## 12. What the review does not establish (Protocol)

It concerns the 63 flagged criteria only; it counts criteria, not independent mistakes; it does not measure score effects; it does not extend to the full benchmark; and "the bound covers sampling uncertainty, not reviewer error." One reviewer, who is also the project author, applied the protocol.

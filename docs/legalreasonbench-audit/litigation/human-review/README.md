# Human review of AI-flagged LegalReasonBench criteria: protocol

This protocol was written and committed on October 24, 2026, before the sample was drawn and before the reviewer examined any sampled criterion. In the pull request that adds it, the protocol commit comes before the commit that draws the sample. It follows the substance of the [Harvey LAB human-review protocol](../../../harvey-lab-audit/litigation-dispute-resolution/human-review/README.md), including that protocol's later clarifications, with the differences stated below.

## Question

Two AI models independently audited the 179 rubric criteria in the 11 litigation assignments of micro1's public LegalReasonBench sample (see the [comparison](../comparison.md)). Either blind report labeled 63 of them problematic or arguable. Those are AI flags, not demonstrated errors. This review asks how many of the 63 flagged criteria are actually defective.

## Sample

- **Unit.** A distinct assignment–rubric-criterion pair, identified by assignment ID and the upstream criterion ID. It is not an AI finding, an underlying mistake, a document, or a matter. A criterion that repeats a point from another assignment is a separate unit.
- **Population.** The 63 rows of [`comparison.json`](../comparison.json) that GPT-6 Sol's blind report or Claude Opus 5.5's blind report labeled `problematic` or `arguable`, deduplicated by assignment–criterion pair. All five agreement buckets are included: both problematic (9), both arguable (6), different strength (16), GPT-6 Sol only (20), and Claude Opus 5.5 only (12). All 11 assignments are eligible.
- **Reconciliation is metadata, not eligibility.** The later reconciliation, which saw both blind reports, retained 36 of the 63 criteria (13 problematic, 23 arguable) and none outside them. The other 27 stay in the population. Each sampled item records its reconciliation status, and the tally reports it descriptively.
- **Not the Harvey frame.** The Harvey population combined GPT-6 Sol's flags with Claude Opus 5.5's final position *after* reconciliation; it excluded 89 Opus blind-pass flags that Opus withdrew on reconciliation and 7 GPT-6 Sol entries that were not final flags. This population is the union of the two *blind* passes. The two frames therefore describe different review stages, and the two results are not estimates of the same quantity.
- **Ordering.** The population is sorted by (assignment ID, criterion ID) with Python's ordinary string comparison, so `criterion_10` sorts before `criterion_2`. The sorted list is saved in `sample.json`.
- **Draw.** A simple random sample of **25** criteria without replacement: `random.Random(20261024).sample(population, 25)`. The seed is this protocol's date. There is no stratification; no quotas by matter, category, or model; no exclusions for convenience or prior exposure; and one draw only, with no replacements, redraws, or additions. Every sampled item is reviewed, and the review does not stop early. The worksheet groups items by assignment for reading, which does not change membership.
- **Reproducibility.** [`scripts/legalreasonbench_review_sample.py`](../../../../scripts/legalreasonbench_review_sample.py) `draw` builds the population and draws the sample. It records the dataset revision, the commit that last changed `comparison.json`, the ordered population IDs, the population and sample sizes, the seed, the algorithm, the Python version, and the selected IDs in draw order. It checks the dataset's current Hugging Face revision against the pinned revision `1bfa904c8f255925baf2610c0f86aa7c05d94ed9`. If the two differ, it records the difference and keeps the pinned revision. It also confirms that the saved criterion text and points match the pinned upstream `rubric.json`. The `tally` command recomputes the draw and refuses to count a worksheet that does not match it.

## What the reviewer decides

The unit is the rubric criterion. The question is whether the criterion, applied as written to the task as given, would misgrade a permissible competent response, not whether an AI's write-up is persuasive. The task as given includes the current prompt and its stipulations, earlier prompts in the same matter, the accumulated attachments, and the stated research universe. In a closed-universe assignment, outside authority can show that supplied law is wrong but does not enlarge what the solver was permitted to use. A penalty criterion is judged the same way: would imposing the penalty as written misgrade a permissible competent response? The reviewer records the fields below for each item in the [worksheet](worksheet.md).

### 1. Rubric verdict

- **Defective.** Applied as written to the task as given (instructions, supplied documents, and governing law), the criterion would grade a competent response wrong on the point it covers. It would either fail a response that a careful litigator would consider correct, or pass one that is wrong. It does so for at least one of these reasons:
  - (a) the expected answer contradicts, or is unsupported by, the supplied record;
  - (b) it states or depends on an incorrect legal proposition;
  - (c) it requires something the instructions did not ask for and that a competent lawyer would not reasonably infer; or
  - (d) it conflicts with the instructions or with another criterion, so a competent response cannot satisfy both.
- **Arguable.** Reasonable litigators could disagree about whether the criterion would misgrade a competent response, or the problem would affect only unusual responses.
- **Not defective.** The criterion grades correctly. This includes a demanding but defensible standard; a judgment call where the criterion takes a reasonable side; a stylistic preference stated in the task; a document inconsistency that does not change what the criterion requires; and an instruction in a fictional or hypothetical record that a response can reasonably follow, even where it misstates real-world law.
- **Unresolved.** The reviewer cannot decide from the record and the available authority.

There is no separate severity scale. Materiality is part of the definition of Defective, and borderline or low-impact concerns are Arguable.

Two recurring situations are decided as in the Harvey review:

- **Criteria that require one of several permissible approaches.** A criterion may prefer one approach. It is Defective when it rejects an approach a careful litigator would adopt on this record. Requiring one permissible option is not by itself a defect; rejecting a correct one is.
- **Defects in the environment.** An unplanted error in the supplied record (conflicting figures, arithmetic that does not add up, fabricated or misdescribed authority) makes a criterion Defective when it changes what a competent response can get right, so that the expected answer is contradicted or unsupported by the record. A criterion can also be defective by passing work that is wrong. When the record is objectively wrong but the criterion still grades correctly, the verdict is Not defective (an environment-only defect). Planted mistakes that the task asks the solver to catch are not environment defects.

For each Defective verdict the reviewer also records:

- **Defect basis:** *Unambiguous objective error* (the record, the law, the cited authority, or arithmetic contradicts the rubric) or *Professional judgment*. Objective errors are reported as a separate count.
- **Defect arises from environment:** *Yes* if the defect stems from an error in the supplied task materials rather than in the criterion alone; otherwise *No*.

### 2. AI reasoning

Did a flagging model's blind report identify the actual problem? The reconciliation is shown separately and is not scored here.

- **Correct.** At least one flagging model's stated reason is why the criterion is defective or arguable.
- **Partly correct.** A model identified the right issue but misstated part of it, such as the law, the record cite, or the scope.
- **Wrong.** No model's reason holds up. This always applies when the verdict is Not defective, and it also applies when the reviewer finds a defect on a ground the models did not give.

A defect found on a different ground still counts as Defective. The AI-reasoning field reports it separately.

### 3. Task environment

Separately from the rubric verdict, each item records whether its assignment's task environment is **Defective** or **Correct**, with a short explanation when Defective. The environment verdict turns on objective errors in the supplied record, or task materials that direct work product a competent litigator should not put before a court, whether or not they touch the sampled criterion. Environment verdicts are reported in their own table against the rubric verdicts and do not enter the estimate below.

### 4. Note and source locator

One or two sentences giving the reason, with the document and passage or the authority relied on.

## Procedure

1. For each item, read the assignment instructions, the earlier same-matter prompts, the criterion, the relevant supplied documents, and the AI findings, and weigh the AI arguments against the sources. The worksheet collapses the blind AI findings and the later reconciliation into separate sections for readability. That is not reviewer blinding, and the reviewer need not form a view before opening them.
2. Check claims against the original LegalReasonBench files at the pinned revision (links are in the worksheet) and, where a ground is legal, against the governing authority, not against quotations in the AI reports. The extracted text and AI visual transcriptions are reading aids with stated limits. Where a scanned page, image, or table cannot be read reliably, say so in the note.
3. Record the fields in [`worksheet.md`](worksheet.md). Once all 25 items are complete, run `uv run python scripts/legalreasonbench_review_sample.py tally`.
4. After the tally, verdicts change only to fix clerical errors, and any such change is noted in the worksheet.

## Analysis (fixed in advance)

**Only Defective verdicts count toward the estimate.** Arguable, Not defective, and Unresolved items stay in the denominator of 25. With *x* Defective of 25, the tally reports:

- the sample proportion *x*/25 and the estimated number of defective criteria among the 63, round(63 · *x*/25);
- the exact one-sided 95% hypergeometric lower confidence bound on that number: the smallest *K* for which P(*X* ≥ *x*) > 0.05 when 25 of 63 criteria are drawn and *K* are defective. This is the Harvey review's method, with no normal approximation, and it accounts for sampling 25 of only 63. The result is reported as obtained; no target is set in advance.

The tally also reports, descriptively: counts for every rubric verdict; AI-reasoning counts; environment counts and the rubric-by-environment table; the number of Defective items resting on an unambiguous objective error (with its own lower bound, as a secondary figure) and the number arising from the environment; and the verdicts within each agreement bucket and each reconciliation status. With 25 items these breakdowns indicate patterns but do not establish them.

The tally refuses to treat a blank or invalid field as a completed review. Until every item has a rubric verdict, AI reasoning, an environment verdict, a note, and (for Defective items) a basis and origin, it reports partial counts for completed items, gives no estimate, and exits with an error.

## What this does and does not establish

- **It concerns the 63 flagged criteria only.** It says nothing about the 116 criteria neither blind report flagged, so defective criteria outside the flagged set are not counted.
- **The count is of criteria, not independent mistakes.** One underlying error, or one document repeated across sequential assignments, can make several criteria defective.
- **It does not measure score effects.** No solver responses were graded, and no benchmark score is corrected.
- **It does not extend to the full benchmark.** The result covers the litigation assignments of the public sample at the pinned revision, not the withheld full LegalReasonBench dataset or its other practice areas.
- **The bound covers sampling uncertainty, not reviewer error.** One reviewer, who is also the project author, applies this protocol. An independent second lawyer re-deciding some or all of the 25 items would strengthen the result, and any such review will be reported alongside it.

## Files

- [`sample.json`](sample.json): the frozen draw, with the reproduction metadata listed above and each sampled criterion's AI and reconciliation statuses.
- [`worksheet.md`](worksheet.md): one entry per sampled criterion, with the exact upstream criterion text, direction, and points; pinned links to the criterion, instructions, earlier prompts, and source documents; the blind AI findings and the reconciliation in separate collapsed sections; and blank review fields. `uv run python scripts/legalreasonbench_review_sample.py render` refreshes the supporting material and leaves the review fields unchanged. `draw` refuses to overwrite an existing worksheet.

# Human review of AI-flagged rubric criteria: protocol

This protocol was written and committed on October 4, 2026, before the reviewer examined any sampled criterion. In the pull request that added it, the protocol commit comes before the commit that drew the sample.

## Question

Two AI models audited the 2,858 rubric criteria in Harvey LAB's 52 litigation-dispute-resolution tasks and flagged 835 of them as problematic or arguable (see the [comparison](../comparison.md)). Those are AI flags, not demonstrated errors. This review asks how many of the 835 flagged criteria are actually defective, and specifically whether the evidence supports the claim that **at least 200** ("hundreds") are.

## Sample

- **Population.** The 835 criteria in [`comparison.json`](../comparison.json) that have an agreement bucket: every criterion that GPT-6 Sol labeled confirmed or arguable, or that Claude Opus 5.5 labeled problematic or arguable in its final position. Excluded are the 96 rows that are not final flags: 89 Opus blind-pass flags that Opus withdrew on reconciliation, plus 7 GPT-6 Sol `unverified` or `qualified_check` entries. All 52 tasks are eligible, including tasks the reviewer explored earlier. That exploration was not a criterion-by-criterion adjudication, and a sampled criterion is reviewed under this protocol regardless.
- **Draw.** A simple random sample of **25** criteria without replacement, using seed `20261004` (this protocol's date). There is one draw: no redraws, replacements, or additions. Every sampled item is reviewed, and the review does not stop early.
- **Reproducibility.** [`scripts/harvey_review_sample.py`](../../../../scripts/harvey_review_sample.py) sorts the population by task and criterion number and selects the sample with Python's `random.Random(20261004).sample`. Its `tally` command recomputes the draw and refuses to count a worksheet that does not match it.

## What the reviewer decides

The unit is the **rubric criterion**. The question is whether the criterion is defective, not whether an AI's write-up is persuasive. The reviewer records three things for each item in the [worksheet](worksheet.md).

### 1. Verdict

The verdict uses the same three levels as the AI audits (problematic, arguable, no defect), so human and AI judgments can be compared directly, plus a fourth level for items that cannot be decided.

- **Defective.** Applied as written to the task as given (instructions, supplied documents, and governing law), the criterion would grade a competent response wrong on the point it covers. It would either fail a response that a careful litigator would consider correct, or pass one that is wrong. It does so for at least one of these reasons:
  - (a) the expected answer contradicts, or is unsupported by, the supplied record;
  - (b) it states or depends on an incorrect legal proposition;
  - (c) it requires something the instructions did not ask for and that a competent lawyer would not reasonably infer; or
  - (d) it conflicts with the instructions or with another criterion, so a competent response cannot satisfy both.
- **Arguable.** Reasonable litigators could disagree about whether the criterion would misgrade a competent response, or the problem would affect only unusual responses.
- **Not defective.** The criterion grades correctly. This includes a demanding but defensible standard; a judgment call where the criterion takes a reasonable side; a stylistic preference stated in the task; a document inconsistency that does not change what the criterion requires; and an instruction in a fictional record that a response can reasonably follow, even where it misstates real-world law.
- **Unresolved.** The reviewer cannot decide from the record and the available authority.

There is no separate severity scale. Materiality is part of the definition of Defective, and borderline or low-impact concerns are Arguable.

### 2. AI reasoning

Did the flagging model identify the actual problem?

- **Correct.** At least one flagging model's stated reason is why the criterion is defective or arguable.
- **Partly correct.** A model identified the right issue but misstated part of it, such as the law, the record cite, or the scope.
- **Wrong.** No model's reason holds up. This always applies when the verdict is Not defective, and it also applies when the reviewer finds a defect on a ground the models did not give.

A defect found on a different ground still counts as Defective. The AI-reasoning field reports it separately.

### 3. Note and source locator

One or two sentences giving the reason, with the document and passage or the authority relied on.

## Procedure

1. For each item, read the task instructions, the criterion, and the relevant supplied documents, and form a view **before** opening the collapsed AI findings. This limits anchoring on the AI's framing.
2. Check claims against the original Harvey LAB sources at the pinned commit (links are in the worksheet), not against quotations in the AI reports. Where a ground is legal, read the authority.
3. Record the three fields in [`worksheet.md`](worksheet.md). Once all 25 items have a verdict, run `uv run python scripts/harvey_review_sample.py tally`.
4. After the tally, verdicts change only to fix clerical errors, and any such change is noted in the worksheet.

## Decision rule (fixed in advance)

**Only Defective verdicts count.** Arguable, Not defective, and Unresolved items stay in the denominator of 25. The bound below is the exact one-sided 95% hypergeometric lower confidence bound on the number of defective criteria among the 835 flagged ones.

| Defective out of 25 | Point estimate (of 835) | 95% lower bound | Supports "at least 200"? |
|---:|---:|---:|---|
| 5 | 167 | 70 | No |
| 6 | 200 | 94 | No |
| 7 | 234 | 118 | No |
| 8 | 267 | 144 | No |
| 9 | 301 | 171 | No |
| 10 | 334 | 199 | No |
| **11** | **367** | **228** | **Yes** |
| 12 | 401 | 257 | Yes |
| 13 | 434 | 287 | Yes |
| 14 | 468 | 319 | Yes |
| 15 | 501 | 351 | Yes |
| 16 | 534 | 383 | Yes |
| 17 | 568 | 417 | Yes |
| 18 | 601 | 452 | Yes |

- **11 or more Defective of 25:** the review supports the statement that at least 200 of the flagged criteria are defective (95% confidence). Report the bound actually obtained.
- **10 or fewer:** the review does not support "hundreds." Report the bound actually obtained instead (for example, "at least 171" for 9 of 25), or no claim if the bound is small.

The tally also reports Defective counts by agreement bucket and the AI-reasoning counts. Those are descriptive: with 25 items they indicate, but do not establish, whether agreement between the two models predicts a confirmed defect.

## What this does and does not establish

- **It is a lower bound on the flagged set only.** Defective criteria that neither model flagged are not counted, so the true number may be higher.
- **The count is of criteria, not independent mistakes.** One underlying error can make several criteria defective.
- **The bound covers sampling uncertainty, not reviewer error.** One reviewer, who is also the project author, applies this protocol. An independent second lawyer re-deciding some or all of the 25 items would make the result stronger, and any such review will be reported alongside it.
- **The scope is this audit.** The result says nothing directly about other Harvey LAB practice areas, about how the defects change model scores or rankings, or about real versus fictional litigation records.

## Note added October 4, 2026: model-run grades

After the review began, each worksheet item gained a collapsed block showing how the two published model runs (GPT-6 Luna at xhigh and Claude Opus 5.5 at low) were graded on that criterion by LAB's native judges, with the judges' reasoning and links to the deliverables in [`model-runs/`](../model-runs/README.md). The verdict definitions, sample, and decision rule above are unchanged. The run grades show whether actual responses were passed or failed and why; they are AI judgments that can misapply a criterion, and they do not replace the reviewer's judgment of whether a competent response would be misgraded. A criterion can be defective even if neither run tripped it.

## Note added October 5, 2026: how two situations were decided

During the review the reviewer applied the definitions above in two recurring situations. They are stated here so readers can apply them too.

- **Criteria that require one of several permissible approaches.** A criterion may prefer one approach. It is Defective when its FAIL branch rejects an approach a careful litigator would adopt on this record, for example withholding an entire document that the criterion requires to be partially produced. Requiring one permissible option is not by itself a defect; rejecting a correct one is.
- **Defects in the environment.** An unplanted error in the supplied record (conflicting figures, arithmetic that does not add up, fabricated or misdescribed authority) makes a criterion Defective when it changes what a competent response can get right, so that the expected answer is contradicted or unsupported by the record. A criterion can also be defective by passing work that is wrong, for example accepting figures that do not answer the question asked when the record lacks the data requested. When the record is objectively wrong but the criterion still grades correctly, the verdict is Not defective (an environment-only defect).
- **Task-environment verdicts.** Each item also records whether its task environment is Defective or Correct, judged on objective errors in the supplied record whether or not they touch the sampled criterion. Environment verdicts are reported in a separate table against the rubric verdicts, to show where the two overlap, and do not enter the decision rule above.

Verdicts were finalized after an AI stress test and consistency review, which argued both for and against each call. Those reviews did not change the definitions or the decision rule.

## Files

- [`sample.json`](sample.json): the seed, population size, and the 25 drawn criteria with their AI statuses.
- [`worksheet.md`](worksheet.md): one entry per sampled criterion, with the criterion text from the pinned rubric, source links, the AI findings and model-run grades collapsed, and the verdict fields.

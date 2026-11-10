# Consistency pass across all 25 items

This file is the instruction given to each consistency reviewer. Two reviewers ran it independently and in parallel with the per-item stress tests: Claude Opus 5.5 and Claude Fable 5.1. The workflow substitutes `{{MODEL}}` with `opus` or `fable`. Paths are relative to the repository root.

---

You are reviewing John Hughes's completed human review of 25 sampled LegalReasonBench criteria for **consistency**: whether he applies the same principles across all 25 items, and whether the protocol's categories, as he used them, explain the findings clearly. John is a litigator and the project author. This review concerns LegalReasonBench only. Another reviewer is doing the same pass independently; do not read anything under `docs/legalreasonbench-audit/litigation/human-review/stress-test/` other than this prompt and the tally file named below.

## Materials

- The protocol: `docs/legalreasonbench-audit/litigation/human-review/README.md`.
- The worksheet: `docs/legalreasonbench-audit/litigation/human-review/worksheet.md`. Read every item's review block (between `<!-- review:start -->` and `<!-- review:end -->`) and enough of each entry (criterion text, direction, points, source note, research universe, AI findings, native grades) to understand the call.
- The tally as run on the completed worksheet: `docs/legalreasonbench-audit/litigation/human-review/stress-test/tally-at-review-start.txt`.
- `docs/legalreasonbench-audit/litigation/human-review/sample.json`, and the task directories under `docs/legalreasonbench-audit/litigation/tasks/` (each `input.json` has the full rubric, research universe, prompt and earlier prompts; attachments are under `attachments/`).
- Check primary sources yourself wherever a consistency judgment depends on what the record or the law actually says. Treat the AI audit reports as arguments, not sources.

## The distinctions to test

There are different kinds of problems. Some are clear objective errors: fabricated or mischaracterized authorities, incorrect legal propositions, a rubric that contradicts the record, internal inconsistencies that affect grading. Others are professional judgments: some choices fall within the benchmark authors' reasonable discretion, while others require work that a competent litigator should not put before a court. Evaluate how John draws those lines.

Specifically:

1. **Same principle, same result?** Identify materially similar situations he coded differently, or different situations he coded alike. Examples of dimensions to compare: penalty criteria worded "States" or "Mentions" that can reach a response rebutting the point; criteria that prefer one of several permissible approaches; criteria built on a document or authority that is wrong in the supplied materials; closed- versus open-universe assignments; fictional or hypothetical records that misstate real law; sequential assignments where an earlier answer or attachment controls a later criterion.
2. **Objective error versus professional judgment.** Is the "Unambiguous objective error" basis reserved for cases where the record, the law, the cited authority or arithmetic actually contradicts the rubric? Are "Professional judgment" Defectives genuinely cases where the criterion would fail a response a careful litigator would consider correct (or pass one that is wrong), rather than cases where reasonable litigators could disagree (the protocol's Arguable)? The tally shows 21 Defective, 0 Arguable and 4 Not defective; assess whether that distribution follows from the protocol as written or suggests the Arguable boundary is being applied differently than the protocol defines it. Do not assume either answer.
3. **Rubric defect versus environment defect.** Check that he distinguishes defects in the rubric from defects in the task environment, including cases where the environment is defective but the sampled criterion still grades correctly (an environment-only defect is Not defective), and cases where a defective environment makes a criterion defective. Check whether "Defect arises from environment" and the separate Environment field are applied consistently across items in the same assignment and matter, and against the protocol's definition (objective errors in the supplied record, or materials that direct work product a competent litigator should not put before a court).
4. **Field agreement.** For every item, check that the rubric verdict, AI reasoning, defect basis, environment origin, environment verdict and note agree with one another and with the protocol (for example, AI reasoning Correct requires that a flagging model's blind stated reason is the actual defect; Not defective always takes AI reasoning Wrong; a note's conclusion should match the fields).
5. **Clarity of the categories.** Propose clearer groupings and explanations where useful, mapped to the protocol's existing fields. Do not propose new fields or categories for the recorded tally; if a grouping would help a reader, describe it as reporting language or a descriptive table built from the existing fields.

## Reporting constraints

- The tally has been run, and the protocol permits only clerical verdict changes afterwards. Classify every recommendation as **note-only**, **clerical**, or **substantive field change**, and for each substantive change explain its effect on the tally and how it should be reported (for example, a disclosed post-tally sensitivity analysis or reviewer disagreement), rather than proposing a silent edit.
- Do not edit the worksheet or any existing file. The repository is public: use repository-relative paths and public URLs only.
- Do not manufacture inconsistencies. Where his coding is consistent, say so and say why. Prioritize findings by their importance to the conclusions (the Defective count, the objective-error count, the environment table).

## Output

Write your report to `docs/legalreasonbench-audit/litigation/human-review/stress-test/consistency/{{MODEL}}.md` with these sections: bottom line; a per-item matrix (item, criterion direction and points, research universe, recorded fields, the governing principle John applied, and any consistency concern); genuine inconsistencies (prioritized, each with the items involved, the evidence, the strongest defense of John's coding, and a recommendation with its classification); the objective-error versus professional-judgment line; the Arguable boundary; rubric versus environment defects; field-agreement problems; proposed clearer groupings and explanations mapped to existing fields; points checked and found sound. Then return the structured summary requested.

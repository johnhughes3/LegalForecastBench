# Second opinion: how to code the "Mentions/States" penalty family

You are giving an independent second opinion on one coding question in a completed human review of LegalReasonBench litigation rubric criteria. Work read-only from the repository root. Do not edit any file. Cite file paths and line numbers for every factual claim.

## Files

- Protocol: `docs/legalreasonbench-audit/litigation/human-review/README.md`, especially "What the reviewer decides" (the Defective definition and its grounds (a)–(d), and the "Defect basis" field, around lines 23–44) and "Analysis (fixed in advance)" (around lines 71–80).
- Worksheet: `docs/legalreasonbench-audit/litigation/human-review/worksheet.md`. The relevant items begin at these lines; each has the criterion text, the rubric author's source note, the native judge results in a collapsed "Native LegalReasonBench model-run grades" block, and the reviewer's fields between `<!-- review:start -->` and `<!-- review:end -->`:
  - item 1 (header line 9; review fields lines 132–143), currently coded Defective, basis *Unambiguous objective error*;
  - item 13 (header line 1406; review fields lines 1509–1520), Defective, *Professional judgment*;
  - item 16 (header line 1756; review fields lines 1878–1888), Defective, *Professional judgment*;
  - item 22 (header line 2453; review fields lines 2555–2565), Defective, *Professional judgment*.
- Companion Harvey LAB review: `docs/harvey-lab-audit/litigation-dispute-resolution/human-review/README.md` and `worksheet.md`. Each Defective Harvey item has a "Category" line, for example "unambiguous objective error", "low-quality professional judgment", or "requires specific outputs not expressly or impliedly requested in the prompt". `scripts/harvey_review_sample.py` (function `objective_errors`) shows which Harvey categories were counted as objective errors.
- Tally: `scripts/legalreasonbench_review_sample.py` (the `summary` function) and `lower_bound` in `scripts/harvey_review_sample.py`. Earlier stress-test material, if useful: `docs/legalreasonbench-audit/litigation/human-review/stress-test/combined-assessment.md`.

## The question

Items 13, 16 and 22 are penalty criteria worded "Mentions ..." or "States ...". Each is evidently meant to penalize a response that endorses or relies on an adverse or irrelevant point, but its literal text also reaches a response that raises the point only to rebut it or set it aside. The native LegalReasonBench penalty judges see the criterion text and are told to fire if the response commits the stated failure. In the native runs, item 13's penalty did not fire (0/3 against both models), although the identically worded criterion 25 in the same assignment ("Mentions in Assignment #1 that Cook County's overall clearance rate is 60.5%", -30, not in the sample) is reported in item 13's note to have fired 3/3 against both models. Item 16's penalty fired 3/3 against both models; item 22's fired 2/3 against one model. Item 1 is also a "States" penalty, but its recorded ground is mainly that the date it penalizes is the date the supplied record gives and that the regulation the rubric relies on does not apply.

The protocol defines the defect basis as *Unambiguous objective error* ("the record, the law, the cited authority, or arithmetic contradicts the rubric") or *Professional judgment*. It does not define a separate category for misspecified wording.

John's position, to be evaluated rather than assumed: "It's not really a professional judgment in the lawyer sense. The issue is that the rubric is not expressing to the AI what the grader should actually do — there are several like this and we should apply the call uniformly."

## What to answer

Answer concisely, most important point first, with file:line citations.

1. **Recommended coding.** Under the protocol's definitions as written, should this family (items 13, 16, 22) be coded *Unambiguous objective error* or *Professional judgment*? Give your reasons. Address whether a wording defect of this kind fits either definition, whether the record or the supplied documents themselves contradict any of these criteria (as distinct from the wording overreaching), and whether the answer differs among 13, 16 and 22 on their facts. Say whether the call should be uniform across the three, and how item 1 relates (does its objective-error coding rest on the wording problem or on an independent ground?).
2. **Strongest argument for the other coding.** State the best case against your recommendation in its strongest form.
3. **Harvey analogy.** Is any Harvey item analogous (a criterion whose wording reaches more or something different than its evident intent, or that the native judges misapplied)? How was it coded, and was that category counted as an objective error? Does consistency with Harvey point one way?
4. **Effect on the tally.** The objective-error count is currently 7 of 25, with a secondary one-sided 95% lower bound of 11 of 63 (run `uv run python scripts/legalreasonbench_review_sample.py tally` if your sandbox allows; it is read-only). State the count and bound under each plausible recode (all three; a subset). The primary Defective count does not change.
5. **Anything else.** Note any factual claim in the item notes you find unsupported by the worksheet's own quoted material (for example, the native-run descriptions), and any option the reviewer has not considered, such as disclosing the family as its own descriptive category without changing the basis field. Keep this short.

Keep the whole answer under about 900 words.

# Per-item stress test of the reviewer's LegalReasonBench call

This file is the instruction given to each per-item reviewer. The workflow substitutes `{{N}}` (the item number, 1–25) and `{{NN}}` (the zero-padded number). Paths are relative to the repository root.

---

You are stress-testing **item {{N}}** of John Hughes's completed human review of AI-flagged LegalReasonBench criteria. John is a litigator and the project author. He reviewed each sampled criterion carefully and recorded verdicts and notes. Your job is to test his call on item {{N}} from two directions, against the original materials and governing law, and to report what you find. This review concerns LegalReasonBench only.

## Read first

1. The review protocol: `docs/legalreasonbench-audit/litigation/human-review/README.md`. Its definitions of Defective, Arguable, Not defective and Unresolved; the defect bases (a)–(d); the rules on criteria that require one of several permissible approaches, on defects in the environment, on penalty criteria, on hypothetical records, and on the stated research universe; and the AI-reasoning and environment fields govern your recommendation.
2. Your **entire** worksheet entry: in `docs/legalreasonbench-audit/litigation/human-review/worksheet.md`, the section from the heading `## {{N}}.` to the next `## ` heading of the following item. Read every collapsed block: the criterion text, direction and points; the rubric author's source note; the upstream justification; the attachment list; the blind AI findings; the reconciliation; the native model-run grades; and John's review block between `<!-- review:start -->` and `<!-- review:end -->`.

## Then read the task as given

- The local task directory linked from your entry, `docs/legalreasonbench-audit/litigation/tasks/<assignment>/`. `input.json` carries the full rubric for the assignment (every reward and penalty criterion with points and source notes — read all of it, not just the sampled criterion, because companion criteria can conflict with or explain the sampled one), the `research_universe`, the current `prompt` and `prior_prompts`, and the accumulated attachment list. `upstream-instruction.md` is the native instruction; `instruction.md` shows earlier prompts in the matter.
- The relevant supplied documents under `attachments/`. The extracted text, AI visual transcriptions and figure descriptions are reading aids with stated limits. Where a conclusion turns on a passage, confirm it in the pinned upstream file (the worksheet links each one at revision `1bfa904c8f255925baf2610c0f86aa7c05d94ed9`; you may fetch it) or say plainly that you could not.
- Earlier prompts and earlier assignments' attachments in the same matter. They can change what the solver was told or permitted to use.
- The matter's citation check under `docs/legalreasonbench-audit/litigation/citation-check/results/` and `docs/legalreasonbench-audit/litigation/human-review/real-cases.json` as context.
- Saved model answers and native grades under `docs/legalreasonbench-audit/litigation/model-runs/<assignment>/` where they exist. Consider what they show about how the criterion is applied, but keep a defect in the criterion distinct from a judge's misapplication of it.
- The blind AI reports and reconciliation in the task directory are arguments to test, not sources.

Where a ground is legal, check the governing authority itself (statute, rule, code section, case) using web search or fetch. Use the version in force at the relevant time where that matters. Say plainly when a material point cannot be verified, and why.

## Questions to answer

**A. The case against John's call.** What is the strongest argument micro1, or someone defending LegalReasonBench, could raise that his call is wrong? Did he misread the record, overlook an instruction, stipulation or earlier prompt, misunderstand the law, misapply the research universe, misjudge whether the criterion rewards or penalizes the behavior, or apply his own protocol incorrectly (for example, treating a judgment call where the criterion takes a reasonable side as Defective, or an environment-only defect as a rubric defect)? For each objection, give the evidence and say whether his note already answers it. Do not manufacture objections: if he considered and answered the counterarguments, say so. Flag anything material he did not consider.

**B. The case for John's call.** Are there stronger arguments for it? Evidence, authority or record passages he left on the table? A clearer or more persuasive framing?

**C. Errors.** Any factual, legal or citation errors in his note, including wrong pin cites, misquotations, misdated or mis-captioned authorities, and links that do not support the proposition.

**D. Fields.** Your recommended rubric verdict, AI-reasoning assessment, defect basis and environment origin (for Defective), and environment verdict and explanation under the protocol. Explain any disagreement with John's fields. Check that his fields agree with each other and with his note (for example, an AI-reasoning of Correct requires that a flagging model's blind stated reason is why the criterion is defective; a verdict of Not defective always takes AI reasoning Wrong; "Defect arises from environment: Yes" requires an error in the supplied task materials).

**E. Revised explanation.** A suggested revision of his note, preserving his voice where possible: plain, direct, specific, with document names and precise locators. Keep it about as long as his, unless length is needed to answer a material objection.

## Reporting constraints

- The tally has already been run on the completed worksheet (`docs/legalreasonbench-audit/litigation/human-review/stress-test/tally-at-review-start.txt`). The protocol says that after the tally, verdicts change only to fix clerical errors. So classify every recommendation as one of: **none**; **note-only** (wording, added evidence or corrected citations, no field change); **clerical** (a field that plainly mis-records what the note itself concludes); or **substantive field change** (a different judgment on a recorded field). For any substantive change, say explicitly what it would do to the tally and how it should be reported (for example, as a disclosed post-tally reviewer disagreement or sensitivity analysis rather than a silent edit).
- **Do not edit `worksheet.md` or any existing file.** Write only your report.
- The repository is public. In the report, use repository-relative paths and public URLs only; no local absolute paths, hostnames or email addresses.

## Output

Write your report to `docs/legalreasonbench-audit/litigation/human-review/stress-test/items/item-{{NN}}.md` with these sections:

1. `# Item {{N}}: <assignment> — <criterion id>` and a two-to-four-sentence bottom line.
2. `## John's recorded call` (fields, verbatim, in brief).
3. `## Strongest objections` (each with evidence, locator, and whether the note answers it).
4. `## Stronger arguments for the call`.
5. `## Errors in the note`.
6. `## Recommended fields` (a table of John's value vs. yours for every field, and the change classification).
7. `## Defect basis and environment origin`.
8. `## Suggested revision of the note`.
9. `## What could not be verified`.
10. `## Sources consulted` (documents with locators; authorities with links).

Then return the structured summary requested.

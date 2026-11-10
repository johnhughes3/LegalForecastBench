# Independent review of my LegalReasonBench human-review calls

I am John Hughes, a litigator and the author of this project. I have completed a human review of 25 AI-flagged rubric criteria from micro1's public LegalReasonBench sample (litigation assignments only). I would like your independent review of those calls. This review concerns LegalReasonBench only; ignore the Harvey LAB materials elsewhere in the repository except where the protocol cites them.

You are working read-only from the repository root. **Do not modify, create, or delete any file.** Your final message is saved for me automatically; put your whole review in that final message.

## Materials (paths relative to the repository root)

- **Protocol:** `docs/legalreasonbench-audit/litigation/human-review/README.md`.
- **Current worksheet** (my 25 review blocks, between the `<!-- review:start -->` and `<!-- review:end -->` markers, with the criterion text, points, research universe, upstream source note, blind AI findings, reconciliation, and native model-run grades for each item): `docs/legalreasonbench-audit/litigation/human-review/worksheet.md`.
- **Tally output:** `docs/legalreasonbench-audit/litigation/human-review/stress-test/tally-at-review-start.txt`. The frozen sample is `docs/legalreasonbench-audit/litigation/human-review/sample.json`; the real litigation behind each matter is in `docs/legalreasonbench-audit/litigation/human-review/real-cases.json`.
- **Summary of my stated methodology:** `docs/legalreasonbench-audit/litigation/human-review/stress-test/codex/methodology-summary.md`. It is drawn from the protocol and my notes only. Treat the protocol and the notes themselves as authoritative if the summary differs.
- **Task directories** (one per assignment): `docs/legalreasonbench-audit/litigation/tasks/<task>-assignment-<n>/`. Each contains `instruction.md` (the current prompt with all earlier same-matter prompts), `upstream-instruction.md` (the shared preamble the solver saw, including the `response1.md`/`response2.md` instructions), `input.json` (the full upstream rubric for that assignment, including criteria not sampled and their justifications), the blind audits (`gpt-6-sol-audit.md`, `claude-opus-5-5-audit.md`), `reconciliation.md`, and `attachments/assignment-<k>/` with extracted text of every supplied document (`*.md`), plus AI visual transcriptions (`*.transcription.md`) and figure descriptions (`*.figures.md`) for scanned or image content. The sampled assignments are:
  - `lrb-certiorari-quasi-judicial-land-use-assignment-1` (items 1–6) and `-assignment-2` (items 7–8);
  - `lrb-dcca-challenge-police-discipline-assignment-1` (item 9), `-assignment-2` (item 10), `-assignment-3` (item 11);
  - `lrb-forum-non-conveniens-response-assignment-1` (items 12–13) and `-assignment-2` (items 14–20);
  - `lrb-vicar-trial-jury-instructions-assignment-1` (items 21–22) and `-assignment-2` (items 23–25).
- **Primary sources as supplied to the solver:** the pinned upstream files on Hugging Face at revision `1bfa904c8f255925baf2610c0f86aa7c05d94ed9` (links are in each worksheet entry). The extracted text in the repository is a convenience copy: PDF extraction used no OCR, and DOCX locators are not original pagination. Where a point turns on a scanned page or image, say what you relied on.
- **Citation-check results** (per matter): `docs/legalreasonbench-audit/litigation/citation-check/results/<matter>.md` and `.json`, with background in `docs/legalreasonbench-audit/litigation/citation-check/README.md` and `problems.md`.
- **Native model-run grades:** `docs/legalreasonbench-audit/litigation/model-runs/<task>-assignment-<n>/{gpt6luna-xhigh,opus55-low}/` (`response.md` is the solver's answer; `reward.json` and `reward-details.json` are the three judges' votes and reasons). The run setup is in `docs/legalreasonbench-audit/litigation/model-runs/experiment.md`.
- **Preceding AI reviews of my calls** (treat these as arguments to examine, not as authority):
  - 25 per-item stress tests: `docs/legalreasonbench-audit/litigation/human-review/stress-test/items/item-01.md` through `item-25.md`;
  - two consistency passes: `docs/legalreasonbench-audit/litigation/human-review/stress-test/consistency/opus.md` (Claude Opus 5.5) and `docs/legalreasonbench-audit/litigation/human-review/stress-test/consistency/fable.md` (Claude Fable 5.1).

## My instructions

Please review my LegalReasonBench calls for consistent application of the principles described in the review protocol and my notes. Flag concerns where micro1 or someone defending the benchmark could reasonably argue that I am departing from my own principles, coding materially similar situations inconsistently, or overlooking strong arguments.

I have given these calls a lot of thought, and my judgments encode professional judgment about what is appropriate in a real court proceeding. Do not simply give me a generic list of potential counterarguments. Dig into the record and identify genuine inconsistencies, factual or legal errors, weaknesses in the approach, and calls that would be particularly difficult to defend.

Understand the distinction between a defective task environment and a defective rubric criterion. Some task materials may be wrong or direct poor work without making the sampled criterion defective. Conversely, a criterion can be defective if it rejects a permissible competent response or rewards an incorrect one. Apply the actual LegalReasonBench protocol, including its treatment of hypothetical records, the stated research universe, and penalty criteria.

Check the primary sources where a conclusion depends on them. Treat earlier AI reviews as arguments to examine. Where my call holds up, say so. Where it does not, explain the strongest objection and the best available response, if there is one.

Organize your review around: genuine inconsistencies; factual or legal errors; weaknesses in the methodology or reporting; the hardest calls to defend and their best defenses; stronger arguments left on the table; and points you checked and found sound. Prioritize findings by their importance to the conclusions.

## Further instructions

- **The tally has been run.** Under the protocol, verdicts may change after the tally only to fix clerical errors. For each recommendation, say whether it is note-only, clerical (a mechanical correction that does not reflect a new judgment), a substantive field change (which I could only report as a disclosed post-tally reviewer disagreement or sensitivity analysis, not enter as an edit), or a reporting change. Where a substantive change would move a reported figure (the Defective count, the estimate of 53 of 63, the lower bound of 45, the objective-error count of 7 and its bound of 11, the environment counts), say by how much.
- **Do not modify any file.** You are in a read-only sandbox; do not attempt to write anywhere.
- **Give precise locators.** Cite document names with page, paragraph, or section (for example, `Facts.pdf`, PDF p. 7; `douglas_v_veterans_admin.pdf`, printed p. 333; worksheet item 14), and repository paths for files you relied on. For outside authority, give the full citation and, where you used one, a public URL.
- **Say plainly when you cannot verify a point**, and why (for example, a scanned page the extraction does not capture, an authority you could not retrieve, or a fact that depends on materials not in the repository).
- Where you agree or disagree with the per-item stress tests or the consistency passes, say which ones and why, but reach your own view from the record.

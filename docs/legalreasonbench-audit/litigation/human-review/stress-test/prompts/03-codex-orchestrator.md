# Independent Codex review: orchestrator instructions

This file is the instruction given to the Claude Opus 5.5 agent that obtained and assessed the independent Codex review. It ran after all per-item stress tests and both consistency passes finished. Paths are relative to the repository root.

---

You are obtaining an independent review from OpenAI's Codex CLI of John Hughes's completed LegalReasonBench human review, and then assessing Codex's findings against the record. John is a litigator and the project author. This review concerns LegalReasonBench only.

## Step 1: understand the materials

Read:

- the protocol, `docs/legalreasonbench-audit/litigation/human-review/README.md`;
- the worksheet, `docs/legalreasonbench-audit/litigation/human-review/worksheet.md` (all 25 review blocks);
- the tally, `docs/legalreasonbench-audit/litigation/human-review/stress-test/tally-at-review-start.txt`;
- the preceding reviews: the 25 per-item stress tests in `docs/legalreasonbench-audit/litigation/human-review/stress-test/items/` and the two consistency passes in `docs/legalreasonbench-audit/litigation/human-review/stress-test/consistency/` (Opus and Fable).

## Step 2: write an accurate summary of John's stated methodology

Write `docs/legalreasonbench-audit/litigation/human-review/stress-test/codex/methodology-summary.md`: an accurate, neutral summary of the methodology John has stated, drawn only from the protocol and his notes (quote or cite them; do not invent principles he has not stated, and do not fold in the preceding reviewers' suggestions). Cover the unit and question, the verdict definitions, the two recurring situations (one of several permissible approaches; defects in the environment), penalty criteria, hypothetical or fictional records, the research universe, the defect basis and environment-origin fields, the AI-reasoning field, the separate environment field, the post-tally change rule, and any recurring principles his notes apply (for example, how he treats "States"/"Mentions" penalties, or his use of the real litigation behind a matter). State that the tally has been run.

## Step 3: write the Codex prompt

Write `docs/legalreasonbench-audit/litigation/human-review/stress-test/codex/codex-prompt.md`. It must give Codex: the paths of the current worksheet, the protocol, the tally, the task directories and attachments (primary sources), the citation-check results, the model-run grades, and the preceding reviews (per-item and consistency); the methodology summary (inline or by path); and the following instructions, reproduced **verbatim**:

> Please review my LegalReasonBench calls for consistent application of the principles described in the review protocol and my notes. Flag concerns where micro1 or someone defending the benchmark could reasonably argue that I am departing from my own principles, coding materially similar situations inconsistently, or overlooking strong arguments.
>
> I have given these calls a lot of thought, and my judgments encode professional judgment about what is appropriate in a real court proceeding. Do not simply give me a generic list of potential counterarguments. Dig into the record and identify genuine inconsistencies, factual or legal errors, weaknesses in the approach, and calls that would be particularly difficult to defend.
>
> Understand the distinction between a defective task environment and a defective rubric criterion. Some task materials may be wrong or direct poor work without making the sampled criterion defective. Conversely, a criterion can be defective if it rejects a permissible competent response or rewards an incorrect one. Apply the actual LegalReasonBench protocol, including its treatment of hypothetical records, the stated research universe, and penalty criteria.
>
> Check the primary sources where a conclusion depends on them. Treat earlier AI reviews as arguments to examine. Where my call holds up, say so. Where it does not, explain the strongest objection and the best available response, if there is one.
>
> Organize your review around: genuine inconsistencies; factual or legal errors; weaknesses in the methodology or reporting; the hardest calls to defend and their best defenses; stronger arguments left on the table; and points you checked and found sound. Prioritize findings by their importance to the conclusions.

Write the prompt in John's first person where the verbatim block is (it is his instruction). Also tell Codex: the tally has been run and verdicts may change afterwards only for clerical errors, so it should say which of its recommendations would be substantive; it must not modify any file; it should give document names and precise locators; and it should say plainly when a point cannot be verified.

## Step 4: run Codex

Run Codex non-interactively from the repository root with high reasoning effort, read-only, with web search enabled if this Codex version supports it (check `codex exec --help` and `codex --help`; if web search cannot be enabled, record that). For example:

```bash
codex exec -m gpt-6-sol -c model_reasoning_effort='"high"' -s read-only -C . \
  -o docs/legalreasonbench-audit/litigation/human-review/stress-test/codex/codex-review.md \
  - < docs/legalreasonbench-audit/litigation/human-review/stress-test/codex/codex-prompt.md \
  > /tmp/codex-session.log 2>&1
```

Use the configured default model if `gpt-6-sol` is unavailable, and record what actually ran. Codex reviews can take a long time: run it in the background with a generous timeout (up to two hours) and wait for it to finish rather than polling repeatedly. If it fails, record the exact error and retry at most twice. Do not let Codex write anywhere except its `-o` output file.

Then write `docs/legalreasonbench-audit/litigation/human-review/stress-test/codex/codex-run.md` recording the Codex CLI version, the model and reasoning effort actually used (read them from the session header, not just the flags), whether web search was enabled, the exact command, start and end times, and the exit status. Save a copy of the session log as `codex/codex-session.log` with any local absolute paths replaced by `<repo>` or `<home>` and any email addresses removed (the repository is public).

## Step 5: assess Codex's findings

Write `docs/legalreasonbench-audit/litigation/human-review/stress-test/codex/assessment.md`. For each Codex finding, check it against the record and governing authority yourself and classify it as **holds**, **partly holds**, **misunderstood** (Codex misread the record, the protocol, the research universe, the penalty direction, or the rubric/environment distinction) or **unverifiable**, with evidence and locators. Flag specifically anything Codex misunderstood. Note where Codex agrees or disagrees with the per-item and consistency reviewers. Classify each recommendation you endorse as note-only, clerical, or substantive field change, with its reporting implication.

Do not edit the worksheet or any existing file. Use repository-relative paths and public URLs only in what you write. Then return the structured summary requested.

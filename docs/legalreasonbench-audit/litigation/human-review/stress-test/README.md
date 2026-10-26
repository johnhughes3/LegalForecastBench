# Stress tests of the LegalReasonBench human review

AI reviews of the project author's completed [human-review worksheet](../worksheet.md), run after the [tally](tally-at-review-start.txt). They are arguments for the reviewer to weigh during the [protocol's](../README.md) quality-control review; the reviewer's resulting decisions are recorded in the worksheet itself.

- [`combined-assessment.md`](combined-assessment.md): the synthesis, with each recommendation classified as clerical, substantive (report as a sensitivity), or note-only.
- [`prompts/`](prompts/): the exact instructions given to each stage, and the [workflow script](prompts/workflow.js) that ran them.
- [`items/`](items/): one stress test per sampled criterion (Claude Opus 5.5, high effort).
- [`consistency/`](consistency/): independent consistency passes by [Claude Opus 5.5](consistency/opus.md) and [Claude Fable 5.1](consistency/fable.md).
- [`codex/`](codex/): the [methodology summary](codex/methodology-summary.md) and [prompt](codex/codex-prompt.md) given to Codex, the [Codex review](codex/codex-review.md) (gpt-6-sol, high reasoning), the [run record](codex/codex-run.md) and sanitized [session log](codex/codex-session.log), and an Opus [assessment](codex/assessment.md) of Codex's findings.

# Native LegalReasonBench experiment

This page records the methods for a native LegalReasonBench experiment in progress. It makes no claim about completed runs, scores, or spend. See the [model-run overview](README.md), the [litigation audit overview](../README.md), and the [human-review worksheet](../human-review/worksheet.md).

## Dataset and scope

The experiment uses the public [`micro1-inc/LegalReasonBench`](https://huggingface.co/datasets/micro1-inc/LegalReasonBench/tree/1bfa904c8f255925baf2610c0f86aa7c05d94ed9) sample at pinned revision `1bfa904c8f255925baf2610c0f86aa7c05d94ed9`. The litigation subset contains four matters, 11 sequential assignments, and 179 rubric criteria, including penalty criteria:

- `lrb-certiorari-quasi-judicial-land-use`
- `lrb-dcca-challenge-police-discipline`
- `lrb-forum-non-conveniens-response`
- `lrb-vicar-trial-jury-instructions`

The task prompts, attachment packets, and upstream rubrics are used as supplied at that revision. The run is a native full-document Harbor task, not a one-shot summary condition.

## Native execution conditions

Harbor `0.24.0` runs the upstream multi-step tasks through OpenCode `1.19.4`. The two solver conditions are:

| Condition | Native model | Variant |
|---|---|---|
| GPT-6 Luna | `openai/gpt-6-luna` | `xhigh` |
| Claude Opus 5.5 | `anthropic/claude-opus-5-5` | `low` |

Within each matter, assignments run in order in one persistent `/app` sandbox. Attachments remain available, and assignment *N* writes `/app/responseN.md` so later assignments can read the prior deliverable. Each assignment starts a fresh agent conversation; the persistence is the task's filesystem state, not carried conversational context. This preserves the benchmark's sequential-lawyer workflow while keeping assignment conversations distinct.

## Native grading and aggregation

Every criterion is evaluated by the same three-judge panel at medium effort: `openai/gpt-5.6-terra`, `anthropic/claude-sonnet-5`, and `gemini/gemini-3.8-flash`. The panel requires all three judges and uses a strict majority: at least two of three judges must pass the criterion. A judge failure leaves the panel incomplete rather than silently reducing the vote count. The panel implementation and task metadata are preserved in the [pinned upstream release](https://huggingface.co/datasets/micro1-inc/LegalReasonBench/tree/1bfa904c8f255925baf2610c0f86aa7c05d94ed9), including the [panel implementation](https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/tests/m1_rewardkit_panel.py) and [task scoring metadata](https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/task.toml).

Required criteria contribute their positive points when met. A penalty criterion represents an error condition: when its majority value is 1, its signed contribution is negative; when it is not triggered, its contribution is zero. Assignment correctness is the sum of signed criterion contributions divided by that assignment's positive-point total, clamped to `[0, 1]`.

For a matter, the public result uses the upstream points-weighted scorer: signed points earned across assignments divided by total positive points, clamped to `[0, 1]`. The `multi_step_reward_strategy = "mean"` setting in each upstream `task.toml` is diagnostic only; it is not the matter score. The repository's [public importer](../../../../scripts/legalreasonbench_model_runs.py) validates the pinned criterion membership, signed weights, polarities, three judge votes, majority values, and assignment aggregation before publishing a complete panel.

## Panel completeness and native diagnostics

The public record separates two questions. “Complete” means that the expected three-judge grade panel is present and validates for every criterion. A native agent exit diagnostic is reported separately on the individual run page and does not, by itself, change a complete grade panel into a failed result. Conversely, a missing or incomplete panel is retained as incomplete accounting and is not treated as a model failure. Responses and native verifier files are preserved without editing or correction.

Results and cost accounting will be added after the native trials finish.

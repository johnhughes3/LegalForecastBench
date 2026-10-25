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

## Reproduction

Download the dataset at the pinned revision above and install the pinned Harbor version. With the appropriate provider credentials available to the native runner, run each matter directory once per condition; Harbor executes its assignments in order:

```bash
harbor run -p "$DATASET_DIR/tasks/<matter>" -a opencode \
  -m openai/gpt-6-luna --ak version=1.19.4 --ak variant=xhigh \
  --jobs-dir "$RUNS_DIR/gpt6luna-xhigh"
harbor run -p "$DATASET_DIR/tasks/<matter>" -a opencode \
  -m anthropic/claude-opus-5-5 --ak version=1.19.4 --ak variant=low \
  --jobs-dir "$RUNS_DIR/opus55-low"
uv run python "$DATASET_DIR/scripts/score_matter.py" "$TRIAL_DIR"
```

Replace `<matter>` with each of the four matter IDs listed above. The two condition directories must contain only the intended native trials; duplicate trials for a matter are rejected during import. After the trials finish, publish their unedited answers and verifier files and refresh the worksheet:

```bash
uv run python scripts/legalreasonbench_model_runs.py import --runs-root "$RUNS_DIR"
uv run python scripts/legalreasonbench_review_sample.py render
```

The importer is an offline publication tool. These commands do not substitute a new solver loop or grading method for the upstream native runner.

## Native grading and aggregation

Every criterion is evaluated by the same three-judge panel at medium effort: `openai/gpt-5.6-terra`, `anthropic/claude-sonnet-5`, and `gemini/gemini-3.8-flash`. The panel requires all three judges and uses a strict majority: at least two of three judges must pass the criterion. A judge failure leaves the panel incomplete rather than silently reducing the vote count. The panel implementation and task metadata are preserved in the [pinned upstream release](https://huggingface.co/datasets/micro1-inc/LegalReasonBench/tree/1bfa904c8f255925baf2610c0f86aa7c05d94ed9), including the [panel implementation](https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-certiorari-quasi-judicial-land-use/steps/assignment-1/tests/m1_rewardkit_panel.py) and [task scoring metadata](https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/tasks/lrb-forum-non-conveniens-response/task.toml).

Required criteria contribute their positive points when met. A penalty criterion represents an error condition: when its majority value is 1, its signed contribution is negative; when it is not triggered, its contribution is zero. Assignment correctness is the sum of signed criterion contributions divided by that assignment's positive-point total, clamped to `[0, 1]`.

For a matter, the public result uses the upstream points-weighted scorer: signed points earned across assignments divided by total positive points, clamped to `[0, 1]`. The `multi_step_reward_strategy = "mean"` setting in each upstream `task.toml` is diagnostic only; it is not the matter score. The repository's [public importer](../../../../scripts/legalreasonbench_model_runs.py) validates the pinned criterion membership, signed weights, polarities, three judge votes, majority values, and assignment aggregation before publishing a complete panel.

## Panel completeness and native diagnostics

The public record separates two questions. “Complete” means that the expected three-judge grade panel is present and validates for every criterion. A native agent exit diagnostic is reported separately on the individual run page and does not, by itself, change a complete grade panel into a failed result. Conversely, a missing or incomplete panel is retained as incomplete accounting and is not treated as a model failure. Responses and native verifier files are preserved without editing or correction.

## Reading the results

These are native benchmark judgments, not human determinations that an answer is legally right or wrong. The worksheet links the actual answer, signed criterion contribution, and all three judges' explanations so a reviewer can compare the grade with the original rubric and source documents. Model grades remain outside the human-review fields and do not alter a human verdict.

This is one execution per model and matter, with different reasoning settings selected to match the earlier Harvey conditions. It does not establish a general model ranking, an error rate for the withheld benchmark, or a causal explanation for score differences. A criterion flagged by the rubric audit does not become a verified defect merely because one of these answers fails it.

Results and cost accounting will be added after the native trials finish.

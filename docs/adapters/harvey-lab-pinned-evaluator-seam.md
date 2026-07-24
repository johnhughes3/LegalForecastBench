# Pinned Harvey LAB evaluator seam

Status: observed against the retained issue-196 pin on 2026-07-16 for `LegalForecastBench-dm0g.4.3.1`.

This characterization decides the upstream boundary that downstream Tier-0 task, deliverable, evaluation, and score contracts may rely on. It is evidence for implementation, not a score and not permission to expose evaluator-private task material.

## Source pin and license

The retained compatibility target is [`harveyai/harvey-labs`](https://github.com/harveyai/harvey-labs) commit `73feb91d63d53b1a44151d99329779c4defcdb72`, tree `944913ee8cdeaef4930a106e5e16d74aa93a29d7`, committed on `2026-07-14T23:51:12-07:00`. No tag points at that commit, so the full commit and tree hashes are the version identity; a branch name is not sufficient.

The checkout carries an MIT license at `LICENSE`, SHA-256 `f92627d2ebe80fc0add3b171b2d7eee5e28a98dd0d0a4a5ee5829314243bb3b9`. Any redistributed upstream material must preserve the Harvey AI, Inc. MIT notice and attribution. LegalForecastBench does not vendor the task documents in this characterization.

The machine-readable observation fixture is [`tests/fixtures/harvey_lab/pinned-evaluator-seam-73feb91.json`](../../tests/fixtures/harvey_lab/pinned-evaluator-seam-73feb91.json). It binds the pin to the exact license, task, document, harness, evaluator, judge, scoring, and report hashes observed during this probe.

## Selected Tier-0 task boundary

The selected task is `employment-labor/identify-issues-in-counterparty-motion-brief`, titled “Identify Issues in Counterparty Motion Brief — WARN Act Partial Summary Judgment.” Its `task.json` SHA-256 is `c117cc3faf49b879f3c475b097bd67293ca79fa5b9e3d9cd91782b0f70f687e4`, and its native deliverable is `issue-identification-memo.docx`.

The solver-visible projection is exactly:

- the `instructions` string recorded in the fixture;
- the eight files under the task's `documents/` directory, with the exact paths, sizes, and SHA-256 hashes recorded in the fixture; and
- the required output basename `issue-identification-memo.docx`.

The upstream `task.json` is a mixed-boundary file and must not be copied wholesale into a solver workspace. Its `criteria` array, including every criterion's `match_criteria`, title, ID, deliverable mapping, and evaluation options, is evaluator-private. A downstream task-materialization contract must project the solver-visible fields while preserving the full pinned `task.json` only in the evaluator boundary.

## Observed native commands

The source checkout exposes the solver command:

```bash
uv run python -m harness.run \
  --model <model> \
  --task employment-labor/identify-issues-in-counterparty-motion-brief \
  --run-id <optional-run-id>
```

Its observed options are `--model`, `--task`, `--run-id`, `--max-turns`, `--temperature`, `--shell-timeout`, `--reasoning-effort`, `--skills`, and `--sandbox-image`. It writes a native run directory beneath repository-local `results/`; the normal solver path contains `config.json`, `metrics.json`, `transcript.jsonl`, `output/`, and scratch `workspace/`. Invalid CLI usage exits 2, an uncaught task, sandbox, adapter, or filesystem failure exits nonzero, and successful completion exits 0; partial run-directory bytes can therefore remain after failure and are not success evidence.

The source checkout exposes evaluation separately:

```bash
uv run python -m evaluation.run_eval \
  --run-id <run-id> \
  --task employment-labor/identify-issues-in-counterparty-motion-brief \
  --judge-model claude-sonnet-4-6 \
  --parallel 6
```

Its observed options are `--run-id`, `--task`, `--judge-model`, `--parallel`, and `--verbose`. A completed `0.0` task score is a valid evaluation and still exits 0; invalid CLI usage exits 2, while task validation, missing run data, extraction, judge, or write failures escape nonzero. `scores.json` is written only after all criterion calls return, and `report.html` only after scoring succeeds. Neither command accepts the previously assumed `--lab-root` or `--output-dir` flag. The existing fixture-oriented Harvey LAB command bridge therefore is not a direct invocation contract for this pinned upstream revision.

Both `--help` probes completed with all recognized provider credential variables removed from the environment. A real evaluator invocation is credentialed: the default judge is `claude-sonnet-4-6` through the Anthropic client, normally using `ANTHROPIC_API_KEY`. DOCX evaluation also requires `pandoc`; alternate judge model prefixes select the upstream Google, OpenAI, or Mistral clients and their corresponding credentials.

The evaluation CLI calls `_load_env` before constructing the judge and reads assignments from checkout-root `.env`. Upstream ignores both `.env` and `.env*`, so a clean Git status and pinned tracked-tree hash do not prove the absence of ambient credentials. The compatibility overlay must fail closed if any checkout-root `.env` or `.env*` entry exists, invoke the pinned `evaluation.run_eval.evaluate_run` function through a trusted wrapper instead of `main`, and launch that wrapper with a fresh `HOME`/XDG environment built from an explicit allowlist of runtime essentials plus only the approved pinned-judge credential. It must never inherit the caller's full environment.

## Evaluator semantics

`evaluation.run_eval` resolves both the task and run from repository-local paths. It reads private criteria from `tasks/<task>/task.json` and candidate bytes from `results/<run-id>/output/`. `config.json`, `metrics.json`, and `transcript.jsonl` are not required to score; `metrics.json` only adds optional cost and document-coverage fields.

The selected task has 23 unweighted binary criteria. Each criterion sends the task title, its private `match_criteria`, and the relevant deliverable text to a separate judge call. The only accepted verdicts are `pass` and `fail`. There is no weighting or rounding: the task score is `1.0` only when all 23 criteria pass and `0.0` otherwise; `n_passed / n_criteria` is diagnostic metadata, not a partial task score.

Missingness is judge-mediated, not fail-closed: when an expected file is absent, the evaluator sends a file-not-found marker to the judge instead of assigning an automatic failure. Filename resolution tries an exact basename, then extension and fuzzy matching, and can invoke an additional fixed Anthropic model for unresolved matching. The compatibility overlay must therefore require the exact expected basename and reject missing, extra, duplicate-basename, symlinked, or hash-mismatched files before invoking upstream evaluation.

The evaluator writes `scores.json`; the CLI then renders `report.html` from that score record. Both contain private criterion-level reasoning and remain evaluator-private until a separate publication policy selects and validates public-safe derivatives.

## Decision: narrow native run-directory overlay

External sealed deliverable evaluation is feasible without rerunning the solver, but only through a narrow compatibility overlay that materializes the trusted deliverable in the pinned evaluator's native layout:

```text
<pinned LAB checkout>/
  results/<fresh-evaluator-run-id>/
    output/
      issue-identification-memo.docx
```

The overlay implementation must verify a clean pinned evaluator identity, reject every checkout-root `.env` or `.env*` entry, verify the task and evaluator file hashes, verify the sealed deliverable hash against its trusted run receipt, create a fresh evaluator-private run directory, copy exactly one regular deliverable file under the expected basename, and invoke the pinned `evaluate_run` function with the selected task and pinned judge model under the allowlist-built environment. The resulting score receipt must bind the LAB commit and tree, task JSON hash, source-document manifest, deliverable hash, evaluator file hashes, judge model, evaluation command, and private score/report hashes.

The overlay must reject dirty evaluator source, symlinks, unexpected files, path escape, a pre-existing run directory, changed bytes after verification, or any attempt to mount rubric material into the solver workspace. It must not pass solver credentials into evaluation or judge credentials into solver execution.

This is deliberately an evaluator overlay, not a reconstructed evaluator and not a reason to weaken the canonical task boundary. Downstream contracts should preserve LAB's native all-pass score and criterion receipts rather than invent weights or a partial aggregate.

## No-credential seam probe

A committed opt-in probe imports the pinned `evaluate_run` function, redirects only its `RESULTS_DIR` to a temporary directory, copies byte-identical DOCX input under the exact expected output basename, and supplies a deterministic local stub judge. The probe starts `uv` with a fresh `HOME`, XDG directories, cache, and an explicit credential-free environment; it also requires the checkout to contain no `.env*` entry. No solver is run and no provider credential is present.

The evaluator accepted a run directory containing only `output/issue-identification-memo.docx`, issued 23 criterion calls, and wrote `scores.json`; `config.json`, `metrics.json`, and `transcript.jsonl` were absent. The source and overlay file hashes matched. This proves path and data-flow feasibility only: the stub's all-pass result is not a substantive LAB evaluation and must never be reported as one.

Re-run the committed fixture checks with:

```bash
uv run pytest -q tests/test_harvey_lab_pinned_evaluator_seam.py
HARVEY_LAB_ROOT=/path/to/pinned/harvey-labs \
  uv run pytest -q tests/test_harvey_lab_pinned_evaluator_seam.py
```

The second form verifies the commit, tree, license, observed source files, task JSON, and all eight solver-visible document hashes against a supplied checkout.

## Claim boundary

This characterization supports implementing a pinned LAB-native evaluation receipt for an externally produced sealed deliverable. It does not establish judge reproducibility, solver containment, trusted receipt verification, or a publishable score by itself. Until the remaining Tier-0 gates and independent review are complete, every public surface remains exactly: “Preliminary — one task pair, operator-run, not independently reproducible.”

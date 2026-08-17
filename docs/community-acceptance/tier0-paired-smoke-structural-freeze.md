# Tier-0 paired Harvey LAB smoke structural freeze

```text
artifact_kind: structural_pre_spend_freeze
artifact_version: 1
bead: LegalForecastBench-dm0g.4.5.14
execution_status: BLOCKED
spend_authority: NONE
approval_target: false
supersession_required: true
```

This artifact freezes the facts that are already supportable before spend. It is deliberately not an executable Tier-0 specification and must not be submitted to the designated approver for spend approval. A later artifact must fill every `BLOCKED` field, carry a new SHA-256, land before any solver or judge call, and explicitly supersede this structural freeze.

Permanent public label: **Preliminary — one task pair, operator-run, not independently reproducible**

## Source and task identity

| Field | Frozen value |
| --- | --- |
| Repository | `https://github.com/harveyai/harvey-labs` |
| Commit | `73feb91d63d53b1a44151d99329779c4defcdb72` |
| Tree | `944913ee8cdeaef4930a106e5e16d74aa93a29d7` |
| Task | `employment-labor/identify-issues-in-counterparty-motion-brief` |
| `task.json` SHA-256 | `c117cc3faf49b879f3c475b097bd67293ca79fa5b9e3d9cd91782b0f70f687e4` |
| Expected deliverable | `issue-identification-memo.docx` |
| Criterion count | `23` |
| Projected manifest SHA-256 | `BLOCKED`: must be generated from the real pinned checkout by the final landed runner |
| LegalForecastBench execution commit | `BLOCKED`: must be the final landed executable-spec commit and an ancestor of `origin/main` |

The exact solver instruction is:

> Review the plaintiff's WARN Act partial summary judgment motion and supporting materials; produce a memo identifying all weaknesses and recommended opposition strategies for the defendant. Output: `issue-identification-memo.docx`.

The solver-visible document inventory is:

| Relative path below the task | Bytes | SHA-256 |
| --- | ---: | --- |
| `documents/briggs-declaration.docx` | 41104 | `335b07d484bf4f7a79f10bc359c6a25a404ecf02d58873e4d1eb3c66c4c563dd` |
| `documents/delaney-class-complaint.docx` | 53588 | `3335c067705d45ef481c7e84016689f6fcfdd154d759983d6aaf0bae42300f35` |
| `documents/greenleaf-answer.docx` | 52095 | `e574825fd238efe28566ec4d2a97bdcdd592ac763be2da67b0967f13add57b0e` |
| `documents/greenleaf-headcount-data.xlsx` | 28748 | `c2d2374b8c2aaa47c2c90b4d9e34e188eb19d86f1fb66ead2c8e3dc7f521bd83` |
| `documents/kowalski-deposition-excerpts.docx` | 47326 | `9de384d305ffdc1082ed27e954cb74853ac1f7dbedaa58b5e12e0d7b56e88eb0` |
| `documents/plaintiff-motion-partial-summary-judgment.docx` | 57337 | `cb07280454e8c332176c24078492f5ad6db92c8e103b3d367d9e9d3fda213029` |
| `documents/plaintiff-sumf.docx` | 43876 | `7aa04d4127d2b9fa195c021c1dcb12fc866ac97351ae18a5ca075b5efbc6d213` |
| `documents/voss-deposition-excerpts.docx` | 55818 | `d4dbfb6e6acf94e1cdbd1a7969091b54f272b6fa039ab6f71c89b12014e90a96` |

The mixed-boundary upstream `task.json`, all criteria and match text, gold material, evaluator source, judge configuration, and other LAB checkout bytes are evaluator-private and must never enter either solver root.

## Paired arms

| Field | Arm A: clean-native Claude | Arm B: native-thin LAB |
| --- | --- | --- |
| Treatment | `claude-code-clean-native` | Pinned upstream native thin solver |
| Requested provider/model | `anthropic:claude-sonnet-4-6` | `anthropic:claude-sonnet-4-6` |
| Resolved provider/model rule | Exact receipt required; unresolved or different identity forbids matched language | Exact receipt required; unresolved or different identity forbids matched language |
| Adapter/runner | Landed internal Claude LAB composition | `BLOCKED`: `dm0g.4.3.7` has not implemented the arm |
| Executable identity | `BLOCKED`: containment targets Claude Code 2.1.220, the landed adapter manifest pins 2.1.231, and the observed installation is 2.1.233 | `BLOCKED`: executable, environment, and wrapper identities are not frozen |
| Model settings | `BLOCKED`: exact settings hash and served identity are not frozen | `BLOCKED`: `--max-turns`, `--temperature`, `--shell-timeout`, `--reasoning-effort`, `--skills`, and `--sandbox-image` are not frozen |
| Native tool policy | Candidate inventory: `Read,Glob,Grep,Bash,Write,Edit` | `BLOCKED`: upstream policy has not been converted into the matched-arm contract |
| Outer containment | `BLOCKED`: no approved privileged whole-process receipt exists for the chosen executable | `BLOCKED`: matched outer envelope is not implemented |
| Auth profile | `BLOCKED`: designated-credential-operator handshake and exact solver/judge profiles remain unresolved | `BLOCKED`: exact solver/judge profiles remain unresolved |

The characterized upstream command prefix is evidence only, not the authorized operator command:

```bash
uv run python -m harness.run \
  --model anthropic/claude-sonnet-4-6 \
  --task employment-labor/identify-issues-in-counterparty-motion-brief
```

## Evaluator and scoring identity

| Field | Frozen value |
| --- | --- |
| Evaluator entry function | Pinned `evaluation.run_eval.evaluate_run`, called through an isolated wrapper rather than the ambient-environment-loading CLI |
| Judge request | `anthropic:claude-sonnet-4-6` |
| Judge temperature | `0.0` |
| Calls per complete arm | `23` criterion calls |
| Total calls for a complete pair | `46`, before any internal retry |
| Verdicts | `pass` or `fail` per criterion |
| Score | `1.0` only if all 23 criteria pass; otherwise `0.0` |
| Metric ID | `harvey-lab-binary-all-pass-v1` |
| Normalizer ID | `legalforecast.harvey-lab-all-pass-normalizer.v1` |
| Issuer ID | `legalforecast.harvey-lab-evaluator-issuer.v1` |
| Issuer key ID | `harvey-lab-evaluator-v1` |
| Algorithm | `Ed25519` |
| Issuer policy SHA-256 | `sha256:8b0b29efb2f044ef6a65d2cea79c832e6c44f6ac00280e00cd5a00265efefb90` |
| Production evaluator receipt | `BLOCKED`: current implementation hardcodes fixture/stub identity and fixture-none policy for its receipt |
| Signer custody/public key | `BLOCKED`: no production authority or custody seam is approved; an ad hoc local key is forbidden |

Evaluation must use the exact output basename, seal each deliverable before evaluator access, and bind the deliverable, projection, wrapper, evaluator, rubric, criteria, aggregation, judge, runtime policy, and complete attempt identities. Output-based unblinding must be disclosed.

## Order, retries, resources, and stopping

- Solver order, evaluator order, opaque arm identifiers, and mapping custody are `BLOCKED`; they must be committed without publishing the private mapping used during review.
- No output-selective retry is permitted. Every attempt, partial output, timeout, failure, and internal judge retry must remain in the private archive.
- A single declared wall timeout is not a monetary stop. Exact per-arm turns/tokens/requests/dollars, per-criterion judge limits, retry limits, parallelism, and one experiment-wide hard stop are `BLOCKED` on `legalforecastbench-e5er`.
- The current Claude manifest's advertised `max_budget_usd` is not an enforced cap because the invocation builder does not emit `--max-budget-usd`.
- Subscription use, if ever selected, must be recorded as `subscription_unallocable`, never as `$0`.

Planning-only administrative reserve: **USD 25–100 for the complete pair**. This is neither an estimate nor a spend ceiling: token limits, internal judge retry behavior, a dated pricing snapshot, and mechanical caps are missing. The executable superseding freeze must replace this band with a reproducible estimate and enforced maximum before the designated approver is asked to approve spend.

## Paths and archive contract

The final runner must require caller-supplied empty roots rather than embed machine-specific paths:

```text
LFB_TIER0_PRIVATE_ROOT/
  projection/
  arm-opaque-01/{solver,scratch,output,quarantine,sealed}/
  arm-opaque-02/{solver,scratch,output,quarantine,sealed}/
  evaluator/{private,overlay,work}/
  receipts/
  attempts/
  review-mapping/
LFB_TIER0_ARCHIVE_ROOT/<experiment-id>/
  archive-manifest.json
  private/
  public/
```

The public allowlist may emit the canonical narrative at `results/community/harvey-lab/claude-code-tier0.md` and hash-bound community package/site artifacts. Raw documents, task rubric, grader material, transcripts, credentials, account data, host paths, private mapping, and non-allowlisted receipts remain private.

## Publication and comparison policy

- Publish only the observed paired difference when every matched-harness identity field agrees.
- Any provider, served model, settings, temporal block, outer envelope, order, resource, or repeat mismatch forces separate system-bundle language.
- Report coverage, score, solve/evaluation/combined costs, token dimensions, solver/evaluator/experiment wall time, summed call time, attempts, retries, and failures as peers.
- Preserve unknown and subscription-unallocable values; do not invent n=1 variance or a generalized effect, superiority, or score-per-dollar ranking.
- Every public surface carries the permanent preliminary label and issue `#49` remains open.

## Independent review protocol for `dm0g.4.5.16`

The reviewer must be independent of every `dm0g.4.5.15` and `dm0g.4.5.18` executor and must verify:

1. The executable spec blob hash and commit predate every solver and judge call.
2. Task, source, instruction, projection, and document hashes match, and both arms received byte-identical solver input.
3. Requested and resolved models, provider, settings, temporal block, outer envelope, order, and repeats match or the publication uses system-bundle language.
4. Containment receipts and canaries establish the frozen host, repository, auth, evaluator-private, and network boundary.
5. Every attempt, timeout, failure, retry, partial output, and cost is retained, with no output-selective retry.
6. Deliverables were sealed before evaluator access with the exact basename and manifest/tree hashes.
7. Evaluator source, wrapper, judge, settings, private material, rubric, criteria, aggregation, token accounting, issuer policy, and signature bindings verify offline.
8. The reviewer recomputes the 23-criterion all-pass score and observed paired difference from authorized artifacts.
9. Coverage, solve/evaluation/combined costs, tokens, wall and summed-call time, attempts, retries, and failures recompute without turning unknown or subscription-unallocable values into zero.
10. The public allowlist is scanned for exact secrets and credential, account, local-path, transcript, raw-document, grader/rubric, private-marker, and mapping shapes.
11. Durable archive hashes and immutable public references verify.
12. `claim_policy.enforce_publication_claims` passes and every public surface carries the permanent preliminary label without claiming issue `#49` closure.

## Conditions for an executable superseding freeze

`dm0g.4.5.14` remains open until `dm0g.4.5.13`, `dm0g.4.3.7`, `dm0g.4.2.2`, `legalforecastbench-lrc3`, `legalforecastbench-e5er`, the designated credential operator's handshakes, exact binary identities, the production evaluator receipt, signer custody, pricing, budgets, order, and archive fields are all resolved and captured in a newly hashed artifact.

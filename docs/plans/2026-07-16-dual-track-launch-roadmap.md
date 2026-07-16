# Dual-Track Launch Roadmap: LegalForecast-MTD Cycle 1 and Community Harness Comparisons

Status: implementation-ready; strategic speed-and-audience amendment incorporated; planning PR open

Date: 2026-07-16

Repository: `johnhughes3/LegalForecastBench`

Roadmap issue: [#203](https://github.com/johnhughes3/LegalForecastBench/issues/203)

Codex CLI harness issue: [#204](https://github.com/johnhughes3/LegalForecastBench/issues/204)

Planning PR: [#205](https://github.com/johnhughes3/LegalForecastBench/pull/205)

Primary owner: John Hughes

Planning branch: `docs/dual-track-launch-roadmap`

Scope: reach the first official LegalForecast-MTD run as quickly and credibly as possible, launch the first real Harvey LAB community harness comparisons with Claude Code and Codex, and converge every open GitHub issue onto an explicit terminal path.

This document is the retained implementation plan and the source for the successor Beads graph.

The live Beads database remains the operational source of truth when its state differs from this dated plan.

## 1. Executive decision

Run two product tracks in parallel, with an integration and issue-convergence lane plus a deliberately small distribution lane that gives each result an audience.

Track O is the official LegalForecast-MTD benchmark.

Track C is the non-official Community Harness Comparisons program, beginning with Harvey LAB tasks executed through Claude Code and Codex.

Track I owns architecture boundaries, release and CI integration, evidence review, and the terminal disposition of the existing GitHub backlog.

Track D owns publication, audience positioning, the LegalQuants engagement loop, and the methods preprint.

The `D-*` prefix is used because `P-*` already names planning/governance packages in this roadmap; it implements the reviewer's proposed publication track without creating ambiguous work-package codes.

Do not turn the repository into a multi-package monorepo before either launch.

The repository already has a meaningful internal boundary under `legalforecast/multiharness/`, distinct community aggregation, and an ADR that treats community comparisons as non-official.

The fastest safe architecture is therefore a modular monolith now, followed by a package split only if the first live pilots prove independent dependency, versioning, or release-cadence needs.

Do not move, rename, or broadly refactor official ingestion code while authenticated acquisition is active.

Acquisition checkpoints, replay hashes, and operator runbooks depend on the current paths and semantics.

Freeze the seam first, land the launches, and reorganize behind compatibility tests afterward.

For the first official run, treat 100 as the launch cohort and 150 as the reserve-pool objective.

Acquire toward at least 150 clean cases in parallel because attrition and later refreshes need inventory, but do not make completion of 150 block the first exact-100 run.

Before any model sees a Cycle 1 packet, create and hash-bind an exact-100 projection from the then-eligible clean pool using a deterministic, output-blind rule.

Cycle 1 has no all-eligible or at-least-150 launch branch.

Any later run over the reserve pool is a separately named extension or cycle with its own freeze, matrix, budget, dispatch, and claims.

The Beads graph currently contradicts the exact-100 launch policy because `5qd6.39` depends on `5qd6.75` and `5qd6.38`.

Resolve that contradiction as an explicit P0 governance task before changing dependency edges.

For community comparisons, use two deliberately different launch tiers.

Tier 0 is a trusted-operator, one-task preliminary experiment that can run within days.

It preserves the pinned CLI's native agent loop, system prompt policy, context management, and native local tools inside a disposable outer boundary; it does not replace those tools with an MCP shim.

Tier 0 freezes the task, arms, model/settings, evaluator, run order, caps, claims, and solver/evaluator separation before spend; publishes only allowlisted, scanned artifacts; and carries the permanent label `Preliminary — one task pair, operator-run, not independently reproducible`.

Tier 0 may progress issue #196, but it does not close contributor-intake issue #49 and is not contributor-safe.

Tier 1 is the full reproducible contributor path.

It retains hostile-input validation, receipts, resume identity, cancellation, trusted score verification, clean rebuilds, submission safety, and contributor documentation.

For Tier 1 and later pilots, build one canonical solve-to-score pipeline:

`pinned task bytes -> harness execution -> canonical deliverable -> pinned LAB evaluator -> canonical score artifact -> validated community package -> comparison site`.

Every harness arm must use the same canonical task materializer and score artifact.

The first Claude Code and Codex runs are allowed to prove plumbing independently, but they must not be described as matched harness comparisons unless solver-visible task content/materialization, served model/provider route/settings, evaluator/judge/scoring revision, project-imposed outer containment, temporal block, resource/stopping rules, and repeat/order-assignment policy are matched.

Harness-intrinsic system prompts, context management, agent loops, and tool APIs are part of the treatment and are therefore excluded from this nuisance-variable match.

Claude Code with an Anthropic subscription and Codex with an OpenAI subscription differ in both harness and model family.

Report those rows as harness-plus-model configurations, not as a clean estimate of harness effect.

The published baseline required by GitHub issue #196 remains an explicit API-key path unless that issue's acceptance criteria are deliberately amended.

Add a separately identified local CLI subscription mode for contributor-owned runs only where provider terms and the installed CLI support that use.

Never infer that a consumer subscription is transferable API entitlement.

Never copy a CLI's durable auth state, account database, token cache, or full home directory into a task workspace or tool container.

The primary scientific profiles are `claude-code-clean-native` and `codex-cli-clean-native`: contain around the harness so its native tools remain part of the treatment.

The whole provider process runs inside a disposable, resource-bounded workspace with isolated HOME/XDG/session state, no repository or ordinary home mount, read-only solver input, a narrow writable output root, evaluator-private bytes absent, and provider-only egress where the installed product contract permits it.

Provider web/browser tools that would bypass the declared boundary are disabled and disclosed.

Do not use Claude Code `--bare` for this arm: the locally installed 2.1.211 binary describes it as a minimal mode that changes the harness being measured.

Keep the GitHub issue #41 network-disabled MCP tool runtime as a separately named `*-mcp-mediated` secondary arm and contributor-security mechanism.

It is useful for decomposing planner versus toolset effects, but it is not the definition of the native Claude Code or Codex harness and does not block Tier 0.

Use at most four active implementation worktrees at peak, including the already-running acquisition lane.

Create at most three new durable worktrees: official eval readiness, community harnesses, and integration/quality.

Staff each ready worktree with up to four primary Codex agents: one integrator and three disjoint owners, for up to 16 primaries plus the coordinator across four lanes when the critical-path queue supports that load.

Each primary may delegate bounded research, fixture, test, or review work, but delegation does not replace clear Bead ownership or file reservations.

Use Agent Mail in every shared worktree, one thread per Bead, exact file/directory reservations, and one writer for shared integration surfaces.

Never claim an `off-critical-path` or `contributor-intake` task while a ready `critical-path-official` or `critical-path-tier0` task exists in the same lane unless the coordinator records why the critical task cannot progress; coordinator-named parallel enablers such as the nonblocking Codex feasibility probe are the only exception.

Land small, ordered PR checkpoints and refresh worktrees from merged `main` between checkpoints.

Do not allow a long-lived branch to accumulate the entire roadmap.

## 2. Outcomes and launch definitions

### 2.1 Outcome O1: first official LegalForecast-MTD run

The first official run uses exactly 100 disclosure-cleared, eligible, label-ready cases whose canonical qualifying decision date is June 30, 2026 or later, selected under a precommitted, hash-bound projection policy.

All 100 cases have complete source, exclusion, purchase, parse, unitization, adjudication, label, packet, and audit provenance.

Every official model packet is frozen before model output is generated.

The official model registry, execution policy, shard schedule, budget ledger, label policy, and publication policy are frozen and mutually hash-bound.

The shard protocol completes a live one-provider smoke before official dispatch.

The official matrix is dispatched only through the canonical `5qd6.41` John-operated freeze and dispatch gate.

Every shard produces an immutable successful completion receipt.

Fan-in verifies the accepted receipt set, exact Cartesian completeness, hashes, object versions, and provenance before aggregation.

The official report is descriptive and uses only claims permitted by the frozen methods and baseline state.

No acquisition-time observation of model outputs influences cohort selection, labels, exclusions, or packet contents.

### 2.2 Outcome C1: first real Harvey LAB community harness run

A preliminary Tier-0 paired smoke is published first from a trusted local operator path.

The primary Claude arm preserves Claude Code's native tools and agent loop inside an outer containment boundary; a nonblocking Codex Tier-0 fast-follow applies the same principle and targets publication within two days of the Claude result.

The native Harvey LAB arm receives byte-identical solver-visible inputs and uses the exact same served model/provider/settings where that can be proven.

If exact model parity is unavailable, the rows are labeled preliminary system bundles and no harness-effect estimate is claimed.

The pinned evaluator runs only after each solver stops and its deliverable is sealed; evaluator-private material is never mounted into the solver boundary.

Score, selected/solved/evaluated coverage, solve and evaluation usage, cost basis, tokens, wall-clock, attempts, and failures are co-equal headline outputs.

Tier 0 is explicitly not the contributor-owned acceptance described below.

At least one pinned Harvey LAB task is solved through a real non-fixture Claude Code adapter.

At least one pinned Harvey LAB task is solved through a real non-fixture Codex CLI adapter.

Both adapters share the same task materializer, execution receipt, deliverable contract, evaluation bridge, score contract, privacy policy, and package validator.

The pinned LAB evaluator scores externally produced deliverables without rerunning the native solver.

At least one paired native-LAB versus external-harness smoke uses the same task, exact model, evaluator, judge configuration, and scoring revision.

If a matched native arm cannot be funded or authenticated yet, the external run remains a plumbing acceptance result and is not called a harness-effect comparison.

The resulting community package passes the existing PR-intake validation and rebuilds the community comparison output.

No official LegalForecast-MTD result path consumes or promotes the community package.

### 2.3 Outcome C2: contributor-owned repeatability

A contributor can clone the repository, point it at a pinned Harvey LAB checkout, select a supported local or API credential profile, run a prespecified task shard, validate the package, and open a results PR without exposing private state.

The command path records CLI version and executable hash, adapter source hash, model request and resolved identity when available, task-selection hash, evaluator identity, auth-mode category, policy hashes, timeout, budget, and result hashes.

The command path never records provider tokens, account identifiers, local credential paths, raw private transcripts, or source matter files in public artifacts.

The package validator rejects unverifiable score artifacts, incompatible groupings, hidden task selection, missing attestations, and unsafe files.

### 2.4 Outcome I1: issue convergence

Every open GitHub issue is mapped to one of five terminal routes: implement, evidence-close, supersede as duplicate, split into a named successor, or milestone-defer with a reactivation condition.

Every active Bead maps to a current issue, plan work package, operational obligation, or explicitly retained future milestone.

Stale `in_progress` records and overlapping official-run epics are reconciled against live code and merged PR evidence.

The final audit leaves no open issue whose owner, dependency, acceptance evidence, or intended milestone is unknown.

### 2.5 Outcome D1: results reach the intended audiences

Cycle 1 has a human-facing report and leaderboard designed for a skimming practitioner or research reader, with the full audit trail one click deeper.

The Tier-0 harness smoke has a short, precise writeup that says what matched, what did not, and what score, cost, tokens, and elapsed time were observed.

John has an approved draft for Jamie and LegalQuants, an explicit invitation to comment before the stratified-pilot task/arm selection is finalized and before any stratified-pilot score is observed, and a bounded feedback window that cannot indefinitely block execution.

The repository README functions as a landing page rather than only an operator manual.

A 6–10 page methods preprint is drafted from `docs/METHODS.md`, then populated from audited results; SSRN submission remains a separate John authorship/publication decision and arXiv is optional.

Official and community pages remain visibly separate and never imply Harvey AI or LegalQuants affiliation.

## 3. Non-goals and fixed boundaries

This plan does not authorize model evaluation during ongoing acquisition.

This plan does not authorize official freeze or dispatch before corpus, labels, packets, budgets, and adjudication gates are complete.

This plan does not make Harvey AI, Harvey LAB, or Legal Quants an official partner or sponsor.

This plan does not rank LegalForecast-MTD Brier scores against Harvey LAB rubric scores.

This plan does not combine scores across suites into one overall winner.

This plan does not publish raw legal source documents, private provider transcripts, hidden evaluator material, credentials, or account identifiers.

This plan does not bypass provider terms, CLI policy, secure-gate, protected environments, or repository publication guardrails.

This plan does not add a second tracker, initialize a second Beads store, or treat the stale passive JSONL export as live truth.

This plan does not replace the already-completed `054` multi-harness platform epic.

This plan does not create a fourth official run bead alongside `ue7.32`, `ur6`, and the canonical `5qd6.35`/`5qd6.41` path.

This plan does not duplicate the active branch/worktree cleanup lane owned by `gww5`.

This plan does not weaken exact-model or provider-family disclosure language for label judges.

This plan does not let community work block the official first run.

This plan does not let official corpus availability block Harvey LAB adapter development, which can use pinned LAB tasks and synthetic LegalForecast fixtures.

This plan does not contact Jamie, LegalQuants, or any other external party without John's explicit send approval.

This plan does not call the Tier-0 path contributor-safe, independently reproducible, or sufficient to close issue #49.

## 4. Current-state evidence

### 4.1 Repository structure

The repository is currently one `uv` project named `legalforecast-mtd` with the `legalforecast` console entry point.

Official acquisition, labeling, evaluation, protocol, and publication logic lives under the `legalforecast` package.

Community harness logic already lives under `legalforecast/multiharness/`.

Community aggregation already has a separate implementation under `legalforecast/publication/community_aggregate.py`.

The official aggregate remains separate under `legalforecast/publication/official_aggregate.py`.

The current multiharness system already contains canonical schemas, task loaders, command adapters, conformance checks, deterministic selection and resume, community packaging, validation, aggregation, and static reporting.

The closed `054` epic is the historical implementation record for that platform.

The current command runner produces `sandbox.plan.json` but does not execute a meaningful live tool boundary.

Repository documentation explicitly identifies that limitation.

The current Harvey LAB adapter assumes obsolete upstream flags and cannot be promoted to a live bridge.

The current community run summary records execution identity and status but does not carry a canonical comparable score artifact with per-task metrics and grader identity.

The current examples for Claude and OpenAI are offline fixtures or API-oriented bridges, not real Claude Code or Codex CLI subscription-native adapters.

The root CLI has grown into a high-conflict integration surface.

That makes broad CLI refactoring during launch work a poor trade.

### 4.2 Installed local harnesses

Claude Code is installed locally and exposes noninteractive structured-output execution, exact model selection, no-session-persistence, tool and permission controls, and a maximum-dollar-budget flag.

The locally observed version during planning was `2.1.211`.

GitHub issue #196 was written against Claude Code `2.1.210`; before spend, either run that exact pinned distribution or comment/amend #196 with the replacement version, distribution hash, compatibility evidence, and rationale.

Codex CLI is installed locally and exposes noninteractive JSONL execution, ephemeral mode, user-config and rule suppression, explicit sandbox selection, model selection, and working-directory selection.

The locally observed version during planning was `0.144.5`.

These observations are planning-time evidence, not permanent compatibility claims.

Each adapter must probe its required flags and fail closed on interface drift.

Each live run must record the observed executable version and hash.

### 4.3 Live official-corpus path

`5qd6.73.34` is the active July 13-16 Case.dev enrichment chain from the 3,244-candidate source.

During the amendment, `5qd6.73.37` closed after PR #202 merged and an immutable 911-row checkpoint reconciled 905 authenticated successes, one authorized terminal exclusion, and 2,338 pending from the 3,244-source universe; its artifacts remain explicitly provisional and final-cohort-ineligible.

`5qd6.73.37.1` is the active Firecrawl 5xx recovery/resume child, while `5qd6.73.34.1` separately owns bounded CourtListener HTTP 202 handling.

`yr43.67` is the active replay lane for 22 previously excluded operative complaints after the CourtListener REST fix.

`5qd6.75` expands the clean inventory to at least 150 cases.

`5qd6.39` is the downstream production pass for assembly through final ledgers.

`5qd6.76` is the John-side Infisical parser and labeling folder blocker.

`5qd6.41` is the canonical John-operated official freeze, dispatch, fan-in, and publication gate.

The live graph contains no dependency edge from the active acquisition children into one immutable target-100 reconciliation gate.

The live graph also makes `5qd6.39` wait for the at-least-150 expansion despite a later operator note directing a first exact-100 launch.

Those are graph correctness defects, not reasons to restart acquisition.

### 4.4 Live official-evaluation path

The official sharded evaluation family already exists under `5qd6.25` through `5qd6.35`.

The parallel-ready starts include `5qd6.25`, `5qd6.28`, `5qd6.32`, `5qd6.33`, and `5qd6.34`.

`5qd6.35` owns the live one-provider smoke and verify-only fan-in.

`5qd6.41` owns the official freeze, eight shard dispatches, accepted receipts, fan-in, aggregation, and publication.

`ue7.32` and `ur6` are older overlapping run records and must be reconciled to that canonical path rather than executed as separate protocols.

### 4.5 Live community path

GitHub issue #41 owns the host-owned container tool protocol and runtime.

Its protocol foundation is implemented, but hardened execution, receipt/resume binding, adapter integration, and negative-control runtime evidence remain.

Live Bead `2dnr` is the active implementation record for #41.

GitHub issue #48 owns the Harvey LAB bridge redesign against the actual separate upstream run and evaluate workflow.

GitHub issue #49 is the first real community submission acceptance run.

GitHub issue #196 owns the Claude Code headless Harvey LAB baseline.

No open issue currently owns a real Codex CLI harness adapter.

GitHub issue #44 is Claude Agent SDK work and must remain distinct from Claude Code.

GitHub issue #43 is OpenAI Responses API work and must remain distinct from Codex CLI.

GitHub issue #10 is the current community umbrella and closes only after the real acceptance run succeeds.

### 4.6 Tracker state

The canonical live tracker is `bd` 1.1.0 backed by the centralized Dolt server.

The `br` command requested by the generic Beads workflow skill is not installed in this repository environment.

The repo-local instructions make live `bd` authoritative, so this plan uses `bd` rather than initializing or installing a competing tracker.

At planning time the live database contained 661 Beads: 578 closed and 83 nonclosed.

After the initial conversion, concurrent acquisition work, and this 23-record strategic amendment, the validation snapshot contains 792 records: 584 closed and 208 nonclosed.

The passive `.beads/issues.jsonl` contained only 389 records and had not been refreshed since July 8.

`bv` therefore produced stale recommendations that included already-closed work.

Live `bd dep cycles --json` returned no cycles.

All plan conversion and validation must use live `bd` until a fresh passive export is made.

## 5. Product and naming model

### 5.1 Official product

Use `LegalForecast-MTD` for the official monthly-to-date forecasting benchmark.

Its unit of evaluation is a frozen case and claim/defendant forecast packet evaluated under the official protocol.

Its outputs are official results only after the freeze, dispatch, receipt, aggregate, audit, and publication gates succeed.

Official artifacts must never be produced by community adapters.

### 5.2 Community product

Use `Community Harness Comparisons` as the repository feature name unless approved Legal Quants branding later replaces it.

Treat Harvey LAB as one external suite supported by the community runner.

Treat Claude Code, Codex CLI, Harvey LAB native, Claude Agent SDK, OpenAI Responses, Hermes, OpenClaw, and future harnesses as separate adapter identities.

Every displayed row names both the harness and model configuration.

Do not label the community product `LAB` in a way that implies ownership of Harvey LAB or Legal Quants approval.

The human-language branding decision in Bead `598` may change presentation later but must not block technical pilots or validation.

### 5.3 Repository entry points

Preserve the current `legalforecast` entry point through both launch cycles.

Add a dedicated community subcommand surface under `legalforecast community` or preserve `legalforecast multiharness` with a stable alias.

Defer a second installed console entry point such as `legalforecast-community` until the shared runtime and submission flow are stable.

If added, keep it a thin wrapper over the same typed application services rather than a forked CLI implementation.

Preserve compatibility aliases for any command renamed during post-launch cleanup.

### 5.4 Package split trigger

Remain one `uv` project through the first official and community launches.

Reconsider a `uv` workspace only after measuring at least one of the following concrete pressures.

The community runner needs heavy dependencies that official acquisition must not install.

The community runner and official benchmark require independent release cadences.

The import-boundary audit can express one-way dependencies without circular compatibility shims.

Community contributors need a substantially smaller install surface than the official operator.

Security review benefits materially from separate distributions.

Until then, use internal packages and import tests to obtain most of the separation at much lower migration risk.

## 6. Architecture boundary

### 6.1 Intended internal modules

`legalforecast/ingestion/` owns official source acquisition, screening, disclosure, purchasing, downloads, parsing inputs, and immutable corpus artifacts.

`legalforecast/unitization/` and `legalforecast/labeling/` own official outcome construction and human/LLM adjudication artifacts.

`legalforecast/protocol/` owns official freeze and policy artifacts.

`legalforecast/evals/` owns official forecast solving and scoring.

`legalforecast/publication/official_aggregate.py` owns official aggregation only.

`legalforecast/multiharness/` owns non-official suite loading, harness execution, deliverable normalization, external evaluation, community score contracts, and submission construction.

`legalforecast/publication/community_aggregate.py` owns community aggregation only.

Shared primitives may live in narrow neutral modules such as hashing, JSON I/O, path safety, record validation, and typed artifact references.

Shared primitives must not import official or community orchestration.

### 6.2 One-way dependency rule

Community code may consume explicitly public, typed LegalForecast task projections.

Community code must not import official freeze, official aggregate, or privileged acquisition orchestration.

Official publication must not import community runner or community aggregate implementation.

Official code may call shared neutral guardrails through a narrow interface.

If current imports violate these rules, first add a characterized compatibility test, then extract only the neutral primitive.

Do not perform a directory move merely to make the tree look cleaner.

### 6.3 Artifact boundary

The boundary is enforced primarily by artifact schemas and validators, not directory names.

Official artifacts carry an `official` namespace, cycle identity, freeze hash, and official policy hashes.

Community artifacts carry a `community` namespace, suite identity, adapter identity, task-selection hash, and score-contract version.

No command may reinterpret one namespace as the other.

Promotion from community to official is prohibited.

Public LegalForecast community tasks, if added later, are newly generated projections with their own disclosure decision and hashes.

They are not aliases to private official packet roots.

### 6.4 CLI integration rule

New command implementations should live in typed service modules under `legalforecast/multiharness/`.

The root CLI should only parse arguments, call the service, render structured errors, and return an exit code.

The community integrator owns root CLI edits during each checkpoint.

Adapter agents do not concurrently edit `legalforecast/cli.py`.

An adapter becomes visible to the CLI through a registry or manifest rather than a repeated switch statement where practical.

## 7. Canonical community contracts

### 7.1 Task identity

`TaskManifest` includes suite family, pinned suite revision, task ID, solver-visible source manifest/hash, deliverable-contract version, and public/private classification.

Evaluator, rubric, judge, and scoring identities are deliberately absent from task identity so an unchanged task can be re-evaluated without becoming a new task.

`SelectionManifest` contains the sorted task IDs, selection policy, seed where applicable, stratification labels, and exact selection hash.

Task selection is frozen before comparative scores are inspected.

The task loader rejects path traversal, symlinks outside the suite root, special files, mutable remote references, missing expected files, and source hash mismatches.

### 7.2 Record graph

The canonical provenance graph is:

```text
TaskManifest + SelectionManifest
        |
        v
RunSpec -> ExecutionReceipt -> DeliverableManifest
                                      |
EvaluationSpec -----------------------+
        |
        v
EvaluationReceipt -> ScoreArtifact

ExperimentSpec + ScoreArtifacts -> ComparisonAnalysisArtifact

SubmissionManifest references every applicable hash above.
```

`RunSpec` owns adapter, requested model, auth category, executable/config/tool policies, budgets, repeat index, and intended runtime policy.

`ExecutionReceipt` owns actual executable and served-model identity, execution status, usage, solve cost, timing, runtime-policy evidence, and deliverable hash.

`EvaluationSpec` owns evaluator revision, rubric revision, requested judge, private-material commitment, settings, budget, scoring contract, and evaluator runtime policy.

`EvaluationReceipt` owns evaluator execution status, resolved judge identity, raw private-result hash, evaluation usage/cost/timing, issuer identity, and input hashes.

`ScoreArtifact` owns only deterministic normalized metric observations derived from one evaluation receipt.

`ComparisonAnalysisArtifact` owns coverage, failure tables, aggregates, paired differences, uncertainty, sensitivity, and allowed claim category.

Usage, cost, and timing remain authoritative in execution and evaluation receipts rather than being duplicated into the score artifact.

The public comparison view dereferences those receipts and presents score, coverage, tokens, cost, wall-clock, attempts, and failures as peer fields.

### 7.3 Materialization

One host-owned task materializer creates the execution input tree for every adapter.

The materializer copies or safely projects only allowlisted files.

It verifies source hashes before projection and materialized hashes afterward.

It records file size, mode class, relative path, and content hash without recording local absolute source paths in public artifacts.

It creates one read-only input root and one initially empty writable output root.

It refuses overlapping input/output paths, home directories, repository roots, sockets, devices, FIFOs, and unsafe symlinks.

### 7.4 Deliverable

A canonical deliverable artifact identifies the task, run, adapter, expected output slots, discovered output paths, media types, byte sizes, and SHA-256 hashes.

Output discovery is restricted to the scoped writable root.

Unexpected executable, socket, device, symlink, or oversized output fails validation.

Missing required deliverables fail the row without invoking the evaluator.

Extra outputs are either rejected or explicitly classified under a versioned policy.

The deliverable artifact excludes raw transcripts and provider response bodies by default.

### 7.5 Evaluation

The solve step and evaluation step are separate.

The external adapter produces a deliverable and stops.

The pinned Harvey LAB evaluator then evaluates the same deliverable contract used for the native arm.

The `EvaluationSpec` records pinned source revision, executable identity, judge request, evaluator settings, private-material commitment, input hashes, timeout, cost approval, and evaluator runtime-policy hash.

The `EvaluationReceipt` records resolved judge identity, raw private-result hash, output hashes, usage/cost/timing, and the concrete protected issuer.

Evaluation cannot mutate solver inputs or deliverables.

Evaluation failure is represented explicitly and is never converted into a zero score.

### 7.6 Score artifact

Create a versioned canonical `CommunityScoreArtifact` before publishing comparative results.

It references the task, deliverable, evaluation specification, and evaluation receipt by hash.

It contains typed per-task metric observations governed by a versioned `MetricDefinition`.

Each `MetricDefinition` contains metric/criterion ID, raw range, directionality, weight, unit, rubric identity, aggregation-function identity/hash, evaluator-owned versus project-owned aggregation, missing-criterion rule, and precision/rounding rule.

It records rubric coverage, missing criteria, evaluation status, failure classification, and normalization provenance.

Solve and evaluation costs, latency, token usage, and attempt identities live in their respective receipts rather than the score.

Uncertainty lives in the comparison analysis rather than the per-task score.

Unavailable observations are null with an explicit reason, never silently zero.

Do not invent equal criterion weighting unless the pinned evaluator defines it.

### 7.7 Identity and compatibility keys

`resume_identity` is the exact task/run/config/auth/executable/tool/runtime-policy identity required to reuse execution work.

`configuration_aggregation_key` groups repeated tasks for the same adapter, served model, suite selection, evaluator, and repeat policy.

`evaluation_comparability_key` requires identical solver-visible task commitments, evaluator/rubric/judge/scoring semantics, and permits different harness/model configurations to appear as labeled system bundles.

`matched_harness_key` additionally requires exact solver-visible task bytes/materialization commitment, served-model identity, provider route, model settings, evaluator, judge, scoring revision, temporal block, project-imposed outer filesystem/network containment, execution-order/repeat assignment, and every prespecified exogenous nuisance variable.

Its resource/stopping identity includes wall-clock, spend, token, context, and attempt/retry caps or policies.

If a product-specific resource policy cannot be matched, the result is a disclosed resource-policy/system-bundle comparison rather than an isolated harness comparison.

It deliberately allows harness-intrinsic system prompts, context management, agent loops, tool APIs, tool implementations, and inner sandbox behavior to differ when those frozen differences are the treatment being studied.

The comparison artifact records those treatment differences explicitly.

A secondary MCP-mediated arm receives a distinct adapter/tool-policy identity and may isolate planner-versus-toolset mechanisms; it is never silently pooled with the native arm.

An unresolved served-model identity prevents `matched_harness_key` but does not prevent a clearly labeled system-bundle row.

The validator rejects aggregation or claims that use the wrong key for their estimand.

### 7.8 Run summary

Extend `CommunityRunSummary` to reference `RunSpec`, `ExecutionReceipt`, `DeliverableManifest`, `EvaluationSpec`, `EvaluationReceipt`, and `ScoreArtifact`.

Preserve backward reading of existing fixture summaries through a versioned migration layer.

Do not infer scores from log text or arbitrary adapter-specific files during publication.

Every published score is reachable through a validated content hash from the run summary.

### 7.9 Comparison semantics

Use paired task-level harness reporting only when two configurations share a `matched_harness_key`.

That key is necessary, not sufficient, for a generalized causal claim.

Tier 0 may report only the observed matched paired difference for its pinned task and run; `estimated harness effect`, `performs better`, general superiority, or population-average language waits for the prespecified multi-task/repeat pilot and supported uncertainty.

Use `evaluation_comparability_key` to display clearly labeled system-bundle rows that share the evaluation semantics but differ in harness/model configuration.

Report coverage and failures alongside scores.

Every public per-arm headline table places these fields at the same level:

- selected, solved, evaluated, and jointly comparable task counts;

- task score and criterion coverage;

- solve, evaluation, and total input/output/cache/reasoning tokens where the providers expose them;

- solve, evaluation, and total cost with currency, pricing-basis category, pricing snapshot/hash/date, and provider-reported versus estimated status;

- solver elapsed time, evaluator elapsed time, per-task end-to-end time, full experiment wall-clock, queue time, attempts, and retries; and

- terminal completion or failure classification.

Unavailable usage is null with a reason, never silently zero.

Subscription execution whose incremental price cannot be allocated is `subscription_unallocable`, never `$0`.

Summed task time is distinct from actual wall-clock when work is parallel.

Cost ratios are reported only when currencies and accounting bases are compatible.

Do not create a default composite score-per-dollar ranking; expose the tradeoff frontier and let readers see the dimensions.

For repeats, report paired task differences and mean/median plus dispersion or intervals only when the sample size supports them.

For a one-task pair, report the observed value without invented variance and report attempt/repeat counts separately.

Do not drop failed tasks from one arm while retaining them in another without making the denominator difference explicit.

Prespecify solve completion rate, evaluation completion rate, conditional score over jointly evaluable paired tasks, and sensitivity to missingness.

Use a failure-inclusive utility score only if the suite defines a defensible penalty or the pilot freezes one before results.

Use task-level differences and paired uncertainty in `ComparisonAnalysisArtifact` for a prespecified pilot with enough tasks and repeats.

Do not claim statistical significance from a one-task smoke.

Do not compute a cross-suite overall score.

Do not merge official Brier metrics and LAB rubric metrics into a shared numeric ranking.

### 7.10 Orthogonal provenance evidence

Record execution operator or issuer evidence separately from harness identity, served-model resolution, runtime-policy evidence, evaluator receipt verification, and score-normalization verification.

A trusted score proves how a committed deliverable was evaluated; it does not by itself prove that a contributor used the claimed harness or model.

Project-operated execution and contributor-attested execution therefore carry different factual provenance fields without creating a quality tier or allowing unverifiable claims.

Every public row exposes which evidence dimensions are verified, attested, unavailable, or failed.

## 8. Authentication and execution profiles

### 8.1 Profile taxonomy

Support `fixture_none` for offline tests.

Support `explicit_api_key` for reproducible published baselines where the provider and issue acceptance require it.

Support `local_cli_subscription` for contributor-owned local CLI runs only when provider-supported and explicitly selected.

Support `clean_native` as the primary harness treatment and `mcp_mediated` as a distinct secondary tool-policy treatment.

Reject implicit fallback between profiles.

Record the selected profile category in public provenance.

Do not record token source, account ID, email, organization ID, credential filename, or credential contents.

### 8.2 Claude Code profile

Probe the exact Claude Code version, executable/distribution hash, structured output, model resolution, permission behavior, native tool inventory, stock networked capabilities, and required noninteractive flags before a run.

The locally observed planning version is 2.1.211; issue #196's earlier 2.1.210 observation must be reconciled and the chosen binary/hash pinned before spend.

The primary `claude-code-clean-native` arm preserves the clean-install native agent loop, system-prompt policy, context management, and enumerated local tools inside the outer boundary.

Its capability record explicitly inventories Read, Write/Edit, Glob/Grep, Bash, native Task/subagent functionality when present, the LAB task's required-tool matrix, and every stock capability deliberately disabled.

It configures no task MCP server and does not replace native tools with the issue #41 bridge.

Use structured output, no session persistence, an exact requested model, a bounded external process-group timeout, a maximum-dollar budget where supported, a frozen effort setting, and a frozen native-tool policy.

Do not use `--bare` in the primary arm because the installed CLI defines it as minimal mode and therefore changes the harness treatment.

Isolate project settings, user settings, hooks, plugins, skills, slash-command sources, browser integration, and unrelated MCP servers without changing the native agent loop or local tool implementations.

Use an explicit ephemeral configuration root rather than the user's full configuration directory.

Disable provider-side web/browser capabilities when they can bypass the declared network or task boundary, and record that deviation from ordinary defaults.

Call the result `out of the box` only when every stock capability relevant to the LAB policy is retained or the LAB task policy itself forbids the disabled capability; otherwise use the more precise `clean-install native` description.

A later `stock-networked` exploratory profile may retain allowed stock networked capabilities behind a separately reviewed egress and contamination policy, but it cannot block Tier 0 or be pooled silently with `clean_native`.

If local subscription auth cannot be projected without copying durable token state or exposing the full home directory, fail closed and require the explicit API-key profile.

Record the requested model and resolved model identity when Claude exposes it.

Do not call a subscription-backed run a portable published baseline.

If the native permission mode needed for autonomous execution is not compatible with the verified outer boundary, fail closed or label the narrower profile; do not silently fall back to an MCP-mediated arm under the native name.

### 8.3 Codex CLI profile

Probe the exact Codex version and required noninteractive flags before a run.

The primary `codex-cli-clean-native` arm preserves Codex's clean-install native agent loop, system instructions, context management, enumerated shell/filesystem/search/edit tools, native delegation when present, and native sandbox behavior inside the same class of outer disposable boundary.

Use JSONL output, ephemeral mode, explicit model selection, user-config and rule suppression, explicit working directory, and the narrowest native sandbox compatible with the pinned task.

Do not substitute a foreign MCP tool loop for the primary arm.

Do not expose the repository, full home directory, Codex configuration tree, or auth files to the whole-process native boundary.

If local subscription auth cannot be used without copying durable auth state into a run workspace, fail closed and require an approved explicit credential path.

Record requested and resolved model identity where the CLI exposes them.

Treat Codex CLI as distinct from the OpenAI Responses API adapter in issue #43.

Keep a later `codex-cli-mcp-mediated` arm only if it answers a useful planner-versus-toolset question; it depends on issue #41 and never blocks the first native Codex result.

### 8.4 Host and container split

The primary native profile contains around the whole harness.

Place the provider CLI and its native local tools in a disposable, non-root, resource-bounded OS/container sandbox with a read-only root, isolated HOME/XDG/tmp, no session persistence, no host repository or ordinary home mount, no SSH/Docker/cloud-metadata surface, read-only solver input, an initially empty writable output root, and scratch space.

Only the exact hash-verified solver-visible task projection enters that boundary.

The LAB checkout, rubric, answer keys, evaluator prompt/code/configuration, judge material, and any hidden reference are absent.

Limit egress to the provider endpoints required by the pinned CLI where this can be verified; deny general direct DNS/network and provider web/browser tools.

Seal and hash the output after the solver exits, then invoke the evaluator in a separate boundary with the sealed deliverable read-only and evaluator-private material read-only.

For the trusted-input Tier-0 run, any unavoidable credential projection stays inside the disposable execution boundary; the capability probe records whether native child tools can inherit or read it, and the plan never claims parent-process-only exposure without a passing child-environment/read canary.

Raw streams remain private and public artifacts are built from an allowlist and scanned for exact secrets, secret shapes, account identifiers, credential paths, host paths, and grader canaries.

Tier 0 does not claim that this boundary is safe for hostile contributor tasks.

The secondary `mcp_mediated` profile retains the original host/provider plus network-disabled issue #41 tool-container design.

For that profile, the host mediates versioned JSONL tool requests and responses; every request and response remains receipt-bound as specified by issue #41.

Rows from the two profiles have different adapter/tool-policy identities.

### 8.5 Fail-closed policy

No contributor-supplied task or contributor-grade accepted result runs until the selected native outer boundary or secondary issue #41 mediated boundary and its applicable negative controls pass.

The trusted-operator Tier-0 task may run earlier because it uses pinned public LAB inputs, a physically separate evaluator, a disposable native boundary, a prespecified cap, and allowlist-only publication.

It cannot satisfy #49 or any contributor-safety claim.

A credential-only no-tool handshake may also run earlier to prove CLI invocation and redaction, but it is private, non-comparative, and cannot satisfy #49.

Missing runtime, unsupported capability, interface drift, unknown auth state, unsafe path, unpinned image, or failed negative control stops the run before provider spend where possible.

## 9. Official Cycle 1 cohort policy

### 9.1 Exact-100 launch rule

The official Cycle 1 launch target is exactly 100 cases.

The eligible source pool may exceed 100.

The projection algorithm uses only frozen pre-output case attributes.

The projection optimizes or stratifies only according to the already-approved case-mix policy.

Tie-breaking is deterministic and hash-bound.

No model output, evaluator output, label disagreement observed after selection, or expected difficulty estimate derived from benchmark models may influence projection.

### 9.2 Reserve pool

Continue acquisition toward at least 150 clean cases as a reserve and later extension tranche.

Reserve cases remain outside Cycle 1's exact-100 freeze unless an allowed pre-dispatch replacement rule is triggered.

Replacement events record reason, old and new case identities, policy authority, and a new projection artifact hash.

No replacement occurs after any benchmark model sees the replaced or replacement packet.

The later at-least-150 extension must preserve Cycle 1 artifacts and avoid rebilling or rerunning the original 100 unnecessarily.

### 9.3 Acquisition reconciliation gate

First add a source-universe reconciliation child under `5qd6.73`.

That task inventories every nonclosed `5qd6.73.*` record from live `bd` and classifies it as a required source or recovery input, subsumed by a newer source, optional candidate recovery, operational hardening required for final reconciliation, or stale/superseded tracker state.

The classification, not this dated plan's snapshot, determines the complete blocker set for the target reconciliation gate.

Then add one target reconciliation child under `5qd6.73` with immutable `launch_case_count=100` for Cycle 1.

That gate depends on every required lane identified by the source-universe reconciliation, including the July Case.dev enrichment chain, provisional Firecrawl screening, CourtListener complaint replay, authenticated REST replay, HTML replay, residual Firecrawl complaint fallback, transport defects that affect terminal evidence, and final source reconciliation.

The gate proves full source-set reconciliation, authenticated terminal exclusions, an exact residual pending set, complete exclusion-ledger integration, and an immutable projection input containing at least `launch_case_count` clean eligible cases.

The gate closes only when reconciliation is complete and the eligible count meets `launch_case_count`.

If the pool is short, mark the gate blocked with the exact count, missing evidence, and reactivation condition; activate another acquisition lane without weakening or closing the gate.

Before making `5qd6.73.28` depend on `yr43.67`, confirm that the in-progress fallback is not executing its final residual pass, checkpoint it safely, and regenerate its input from the exact REST-unrecoverable residual set.

Do not spend Firecrawl credits on complaints already recoverable through the merged REST path.

Firecrawl is credit-consuming fallback work, not PACER or document-purchase activity; account for those budgets separately.

### 9.4 Downstream unblock

Record immutable `launch_case_count=100` and make `5qd6.39` the production pass for that cohort.

Use a make-before-break graph migration.

First make the immutable target projection block both purchase decision `5qd6.37` and production pass `5qd6.39`.

Add `5qd6.39.11`, `5qd6.39.6`, and `5qd6.39.10` to the production-readiness chain, with operator/runbook conformance preceding the provider-free downstream rehearsal.

Only after those replacement edges exist and the graph remains cycle-free, remove the direct `5qd6.39` blockers from continuing loop `5qd6.38`, reserve expansion `5qd6.75`, and acquisition umbrella `5qd6.73`, and replace the `5qd6.37` blocker from `5qd6.73` with the immutable projection.

Retain blockers for target-100 reconciliation, purchase decision, Infisical stage folders, and all active correctness children.

Add a separate incremental production/finalization child under `5qd6.75` for the later reserve extension.

### 9.5 John-side decisions

John creates the dedicated Infisical parser and labeling folders for `5qd6.76`.

Parsing and labeling fail closed while either path returns 404.

No broader credential path substitutes for those stage-specific folders.

John records immutable `launch_case_count=100` and the nonblocking reserve boundary before projection freeze.

John confirms label-judge composition and the precise exact-model/provider-family disjointness claim.

John performs the remaining citation check under `5qd6.36`.

John freezes the Cycle 1 model-universe and registry cut no later than 2026-07-20 unless a recorded pre-output decision changes the date.

New models outside that frozen universe normally move to Cycle 2; they do not silently change the Cycle 1 projection.

Every Monday until dispatch, and again within 24 hours before dispatch, the official lane records `eligibility_anchor`, `model_universe_frozen_at`, `registry_cut_at`, any served-model alias/version evidence, `anchor_to_dispatch_days`, and `registry_cut_to_dispatch_days`.

A newly released model outside the universe is a market-freshness event, not automatic invalidation.

Drift in a served alias or model inside the frozen universe is a validity event and requires an explicit continue, replace/reproject-before-output, or defer decision.

Matching a returned alias or model string cannot detect a silent weight roll behind the same name.

The run card and report disclose that residual risk and never describe a provider-served revision as immutable unless the provider exposes a verifiable immutable revision identifier.

John authorizes and operates official freeze and dispatch under `5qd6.41`.

## 10. Official evaluation policy

### 10.1 Canonical run path

`5qd6.35` is the only live smoke and verify-only fan-in gate.

`5qd6.41` is the only official freeze, dispatch, receipt, fan-in, aggregate, and publication gate.

Update `ue7.32` so its remaining rehearsal acceptance is satisfied by evidence from the canonical smoke and official run.

Make `ur6` depend on `5qd6.41` or evidence-close it after that run.

Do not execute a separate legacy protocol merely to close old records.

### 10.2 Parallel engineering before corpus completion

The shard-protocol chain `5qd6.25 -> 5qd6.26 -> 5qd6.27 -> 5qd6.29` may proceed while acquisition runs.

Spend and reservation work under `5qd6.28` may proceed in parallel.

Provider-isolation work under `5qd6.32` may proceed in parallel.

Independent freeze/provenance tasks `5qd6.33` and `5qd6.34` may proceed in parallel.

Each of those lanes lands its own reviewable checkpoint before the live smoke.

### 10.3 Smoke gate

The smoke uses a throwaway nonofficial cycle or explicit smoke mode.

It dispatches one provider shard through the real workflow and credential boundary.

It proves concurrency identity, shard-only execution, exact receipt production, object commitment, resume behavior, and verify-only fan-in.

It proves the cycle-wide reservation ledger under retry and failure conditions.

It does not publish an official report.

Smoke failure produces an operator-readable recovery path and preserves evidence.

### 10.4 Official dispatch gate

The freeze binds exact case IDs, packet hashes, label hashes, model registry, execution policy, shard schedule, budget policy, publication policy, and required receipt schema.

The pre-dispatch audit confirms that the frozen model universe is still the universe actually served and that the June 30 eligibility anchor remains authoritative for every selected case.

Every dispatch matches one declared shard.

Every shard is below the workflow matrix limit.

Concurrency keys include shard identity or an equally proven queueing policy.

Shard jobs do not aggregate or publish.

The finalizer writes one immutable receipt only after every expected cell is present or validly resumed.

Fan-in selects exactly one accepted receipt per shard and rejects ambiguous reruns until an accepted-attempt map is committed.

Official aggregate verifies all expected and no extra cells.

Publication begins only after audit and provenance verification succeed.

The official report shows micro-Brier with confidence intervals, calibration, refusal/invalid rates, realized outcome prevalence, and any genuinely frozen pre-run historical or human reference that exists.

Cycle 1 currently makes no skill-over-baseline claim.

If no valid pre-run empirical base-rate corpus exists, show the predeclared constant `p=0.5` reference (Brier 0.25) only as an unranked uninformed reference and say explicitly that no empirical predictive baseline or Brier skill score is available.

A same-sample constant based on observed prevalence may appear only as a post-hoc oracle reference, never as a prospective forecast baseline.

## 11. Workstream dependency overview

The official and community tracks have no mutual blocking edge.

Both consume shared CI capacity and root CLI integration attention, so the integration lane sequences only those hotspots.

The high-level graph is:

```text
Official acquisition lanes -------------------------------> target-100 reconciliation
        |                                                            |
        +-----------------------> reserve >=150                       v
                                                     exact-100 policy/projection
Official eval engineering -----> official smoke --------------------> downstream corpus
                                                                        |
                                                                        v
                                                              official freeze/dispatch
                                                                        |
                                                                        v
                                                              official publication

Pinned LAB + provider terms -----> Claude native proof -----> Claude Tier-0 paired smoke
             |                           |                              |
             |                           |                              v
             |                           |                   preliminary writeup
             |                           |
             +--------------------> Codex native proof -----> Codex Tier-0 fast-follow
             |                                                          |
             |                                                          v
             |                                                reviewed result addendum
             |
Closed 054 platform -----> score/deliverable contracts -----> contributor-grade native runtime
            |                         |                                  |
            |                         +---------> publication metrics     +--> Claude Code
            |                                                            +--> Codex CLI
            +-----> #41 runtime -----> optional mediated-tool arm         +--> LAB bridge
                                                                            |
                                                                            v
                                                               trusted package/site + pilot

Audience/claims calendar -----> report and writeup shells -----> result pages/README/preprint
             |
             +-----> John-approved LegalQuants engagement -----> bounded pilot-input window

Issue inventory ---------------------> mapping/reconciliation ----------> terminal audit
Architecture ADR --------------------> import/CI guardrails ------------> post-launch split decision
```

The graph deliberately allows official evaluation engineering, Tier-0 native characterization, community contract work, #41 secondary-profile work, audience work, and issue mapping to start while live corpus acquisition continues.

## 12. Worktree and agent topology

### 12.1 Worktree W0: live official acquisition

Purpose: finish the authenticated acquisition and corpus production path without destabilizing live checkpoints.

Existing worktrees and artifact roots remain in place.

Do not create a replacement worktree solely to conform to this plan.

Agent A0 is the sole live-store writer and operator.

Agent A1 owns Case.dev/Firecrawl code and tests but does not mutate live cycle state.

Agent A2 owns CourtListener/complaint recovery code and copied-artifact analysis but does not mutate live cycle state.

Agent A3 owns disclosure/projection/downstream fixture work and independent evidence checks but does not mutate live cycle state.

Maximum simultaneous writers to a cycle store: one.

Owned code: current ingestion/recovery files only when required by the active Bead.

Owned artifacts: the current cycle state store, snapshots, source manifests, exclusion ledgers, and authenticated run evidence.

No community code changes occur here.

### 12.2 Worktree W1: official eval readiness

Purpose: implement the shard protocol, spend ledger, provider isolation, freeze provenance, and smoke gates already represented under `5qd6.25` through `5qd6.35`.

Create one durable worktree from current merged `main`.

Agent O0 is the integrator and the sole writer for `.github/workflows/run-benchmark.yaml` and overlapping root-CLI surfaces.

Agent O1 owns shard schedule, dispatch provenance, finalizer receipts, and fan-in.

Agent O2 owns provider spend, attempt ledger, and accounting tests.

Agent O3 owns provider isolation, runbook conformance, workflow validation, and independent review when file ownership does not overlap.

O0 alone integrates shared workflow files during a checkpoint.

Workflow changes land in isolated PRs and use `secure-gate-elevate` for push.

No acquisition module refactor occurs here.

### 12.3 Worktree W2: community harnesses

Purpose: build the canonical score path, shared local CLI runtime, LAB bridge, Claude Code adapter, Codex adapter, and real community pilot.

Create one durable worktree from current merged `main`.

Agent C0 is the integrator and sole writer for `spec.py`, `runner.py`, shared adapter registry/CLI surfaces, migrations, and conflict resolution.

Agent C1 owns Claude Code native-containment characterization, the Claude adapter module, and its tests.

Agent C2 owns Codex native-sandbox characterization, the Codex adapter module, and its tests.

Agent C3 owns the pinned Harvey LAB projection/evaluator seam, Tier-0 operator path, task/output fixtures, and independent measurement checks.

The Tier-0 path lands first from W2 while C0/C1/C3 work on disjoint reserved files; the contributor-grade foundation continues behind it.

Keep Claude and Codex in W2 while exact file reservations prove their modules do not collide.

If shared-file or review evidence shows that one branch/PR would serialize the adapters, park W3 and recreate that counted slot from merged `main` for an independent Codex PR.

Do not create the extra worktree by default merely because there are two adapters.

Before the shared interfaces freeze, C1 and C2 work only on capability probes, manifest drafts, fakes, and characterization tests.

After the foundation PR merges and the worktree refreshes, C1 and C2 implement adapters in parallel against the frozen interfaces.

W2 is reserved for the native Tier-0 critical path and cannot be occupied by the secondary issue #41 work.

Checkpoint and park the existing #41 branch unless it can land without delaying C-T0a; a preserved but inactive worktree does not count as an active implementation slot.

If #41 must stay active for a bounded landing pass, count it explicitly as temporary W2-M, limit it to two agents, and keep W3 implementation inactive so the total remains four active implementation worktrees.

After #41 lands, refresh that worktree from merged `main` before it takes any later mediated-profile assignment.

### 12.4 Worktree W3: integration, quality, and issue convergence

Purpose: own the boundary ADR, CI path coverage, release checks, documentation, issue mapping, stale-Bead reconciliation, and final evidence audit.

Create this worktree only after the retained plan PR lands, or use the coordinator worktree if the change set stays documentation-only.

Agent D0 owns the Cycle 1 report/leaderboard shell and official result presentation.

Agent D1 owns the harness writeup, README landing page, and preprint draft.

Agent D2 owns audience/claims governance, the Jamie/LegalQuants draft, issue mapping, and Beads evidence; D2 never sends externally.

Agent D3 owns CI/quality integration, community workflow files, and cross-worktree fresh-eyes review.

This lane never rewrites active acquisition history or closes a Bead solely because a comment claims success.

It verifies code, tests, artifacts, PR state, and acceptance evidence first.

### 12.5 Recommended headcount

Target four primary Codex agents in every worktree whose critical-path queue can use them efficiently, plus one cross-lane coordinator.

The maximum planned peak is therefore 16 primary agents plus the coordinator across four implementation worktrees; during a temporary two-agent W2-M landing pass, W3 stays inactive and the practical peak is lower.

This is a capacity ceiling, not a utilization target: do not assign agents to long-tail work merely to fill seats.

Each primary owns a Bead and a disjoint file or operational surface.

Each primary may delegate bounded read-only research, fixture analysis, test generation, or fresh-eyes review to subagents.

Delegated work returns to the owning primary for integration, verification, and the Bead evidence trail.

When a lane is blocked on a merge or human credential decision, move its primaries to another lane's ready critical tasks or review queue rather than create a fifth worktree.

### 12.6 Why this topology

Fewer worktrees preserve shared context and reduce repeated environment setup.

Separate official acquisition from official workflow engineering because live state and workflow files have different failure modes.

Separate community harness work because it has high internal overlap but little need to touch official ingestion.

Keep issue convergence and CI in one lane because both require repo-wide visibility and small cross-cutting edits.

The topology limits the main collision zones to explicit integrators.

Four primaries per lane improve throughput only because Agent Mail reservations and single-writer surfaces make ownership explicit.

### 12.7 Phase-specific worktree slots

Foundation wave slots are W0 acquisition, W1 official integration, W2 Tier-0/community foundation, and W3 audience/integration/issues.

Each shared worktree has one checked-out integration branch and one active PR at a time.

Multiple agents may contribute disjoint commits to that PR under the integrator's file-ownership map.

Separate concurrent PRs require a separate worktree counted against the four-slot ceiling or an explicit Aviator stack.

During the adapter wave, keep both adapters in W2 while reservations remain disjoint; only then, if measured collision pressure warrants it, finish or park W3 and repurpose that freed slot as a temporary Codex worktree while W2 carries Claude.

Claude and Codex therefore receive independent, concurrent PRs without exceeding four active implementation worktrees.

W1 similarly combines disjoint shard/provenance work into one integration checkpoint unless a freed worktree slot is deliberately assigned to a separate PR.

No task may create an uncounted fifth implementation worktree merely because its files are disjoint.

### 12.8 Agent Mail and lane scheduling contract

Register all four primaries under the worktree's absolute Agent Mail `human_key`.

Use one Agent Mail thread per Bead and put the live Bead ID in the subject.

At lane start and after every merge, the integrator posts the file-ownership map and the ready critical-path queue.

Reserve exact files or narrow directories before editing.

Shared surfaces such as `legalforecast/cli.py`, `legalforecast/multiharness/spec.py`, shared runner/registry files, `pyproject.toml`, and workflow YAML have exactly one writer at a time.

Agents stage commits by exact filename and never use another agent's uncommitted changes as a reason to reset, stash, or discard work.

A reviewer from another lane supplies fresh-eyes review for code/protocol/security checkpoints.

Use `bd ready --label critical-path-official` or `bd ready --label critical-path-tier0` first.

While either same-lane critical queue is nonempty, use `bd ready --exclude-label off-critical-path,contributor-intake` for ordinary work and claim only coordinator-named parallel enablers outside those labels.

## 13. Version-control and PR protocol

### 13.1 General protocol

Every execution task begins from a live Bead marked `in_progress`.

Every agent checks current branch, worktree status, active Agent Mail reservations where available, and repo-local instructions before editing.

Every agent stages only the files it changed.

Every logical checkpoint receives a conventional commit with hooks enabled.

Every complex deployable checkpoint receives a PR.

Independent PRs should branch from merged `main`.

Dependent early work uses an Aviator stack and `av` commands only.

Do not use raw `git rebase` on stacked branches.

### 13.2 Refresh protocol

After a checkpoint merges, stop new edits in that worktree.

Record or move any uncommitted task-specific work to its correctly owned branch without touching another agent's files.

Fetch the merged `origin/main`.

For the next independent checkpoint, create a fresh branch or fresh worktree from merged `origin/main`.

For an intentional stack, run `av sync` or `av restack` and verify `av tree` before resuming.

Rerun targeted characterization tests after refresh before adding new behavior when the merged checkpoint changes code, generated artifacts, commands, schemas, protocols, security boundaries, or an interface the next task consumes.

For docs-only or test-only checkpoints that change no runtime interface, record the merge SHA and green applicable checks, refresh from merged `main`, and skip redundant post-refresh characterization with an explicit `not applicable` note.

Never pull, rebase, or swap code under a live acquisition or paid-operation process.

Finish or safely stop the stage, checkpoint its evidence, then refresh code for the next stage.

### 13.3 PR boundary rules

One PR should have one dominant acceptance story.

Protocol/schema changes land before adapters that consume them.

Workflow changes are isolated from unrelated Python refactors.

Paid or credentialed live evidence is linked from the PR or issue but private material is not committed.

Generated comparison data lands separately from the implementation that produced it when review clarity benefits.

Do not combine official acquisition fixes and community adapter work in one PR.

Each fully satisfied GitHub issue receives its own `Fixes #N` line in the PR body.

Partial or foundation work uses `Refs #N` or `Progresses #N` and must not auto-close the issue.

In particular, protocol foundations must not close #41, release preparation must not close #42 before the live OIDC acceptance, and a fixture-only LAB change must not close #48.

### 13.4 Review protocol

Each PR receives a fresh-eyes review by an agent who did not author the dominant code.

Pure wording, planning, and fixture-test PRs may use one focused review and repository-required checks; they do not require the full security review or post-refresh runtime characterization unless they change an executable contract.

Security-sensitive runtime, auth, workflow, purchase, and publication changes receive a second focused review.

Reviewers inspect negative paths and artifacts, not only unit-test counts.

Review findings become Bead comments or child tasks before merge when they are not fixed immediately.

No PR merges with unexplained failing checks, skipped hooks, or unresolved correctness findings.

## 14. Planned PR checkpoints

### 14.1 Portfolio and planning checkpoints

PR P0: retained roadmap, architecture decisions, GitHub umbrella issue, and successor Beads graph export.

PR P1: immutable exact-100 Cycle 1 and reserve policy plus live graph reconciliation.

PR P2: architecture boundary ADR and import/CLI ownership tests.

### 14.2 Official checkpoints

PR O1: shard schedule and dispatch-provenance schema.

PR O2: workflow shard-only mode, shard-aware concurrency, and finalizer receipt.

PR O3: attempt selection, verify-only fan-in, and receipt-bound object verification.

PR O4: cycle-wide reservation ledger, provider isolation, and failure recovery.

PR O5: exact-100 fixture downstream rehearsal and operator CLI conformance.

PR O6: first-100 acquisition reconciliation and immutable projection artifacts.

PR O7: production downstream artifacts, labels, audits, and packet freeze readiness.

PR O8: live smoke evidence and any minimal corrective patch.

PR O9: official run evidence, aggregate, run card, and publication artifacts.

O9 may be evidence-only if the operator run needs no code change.

### 14.3 Community checkpoints

PR C0a: pinned LAB run/evaluator feasibility, Claude native outer-containment feasibility, provider/publication-mode preflight evidence, and the issue #196 amendment.

PR C0b: Codex native-sandbox/outer-containment characterization; parallel and explicitly nonblocking for C-T0a/C-T0b.

PR C-T0a: narrow one-task solver/private projection, native capability evidence, frozen paired Tier-0 specification, and operator dry run.

PR C-T0b: independently reviewed preliminary paired machine/audit artifact package; this may be data-only when the operator path needs no code correction, while D1 solely owns the public narrative and README refresh.

PR C-T0c: separately frozen and independently reviewed Codex Tier-0 follow-on package, reusing the task/evaluator seam without blocking C-T0b.

PR C1: canonical task materializer, deliverable, evaluation, and score contracts with backward-compatible readers.

PR C2: community summary, submission, aggregate, and report propagation of real metrics.

PR C3N: contributor-grade whole-process native containment and hostile E2E for clean-native profiles.

PR C3M: separately identified issue #41 mediated runtime, receipt/resume binding, and negative controls; secondary-profile checkpoint that never gates C6a/C6b/C7/C9.

PR C4: real Harvey LAB run/evaluate bridge against a pinned upstream revision.

PR C5: shared local CLI adapter runtime, capability identity, auth profiles, redaction, and offline fakes.

PR C6a: native-contained Claude Code adapter module and conformance suite in W2.

PR C6b: native-contained Codex CLI adapter module and conformance suite in W2 or, only when measured overlap warrants it, the temporarily repurposed W3 slot.

PR C7: Claude-first live one-task execution and result package.

PR C8: validated #49 submission intake, trusted receipt/normalization verification, aggregate/site rebuild, and issue evidence.

PR C9: Codex live one-task execution and dual-adapter readiness evidence.

PR C10: matched-native and stratified-pilot prespecification, before pilot scores exist.

PR C11: stratified-pilot result package and analysis artifact.

PR C12: contributor documentation and submission policy based on the accepted paths.

PR C13: post-launch CLI extraction and optional entry point after the two live adapters prove the seam.

### 14.4 Distribution checkpoints

PR D0: audience/claims calendar, README landing-page structure, harness-writeup template, and Cycle 1 report shell built from fixtures.

PR D1: preliminary Tier-0 writeup and README result link within 24 hours of validated publication.

PR D2: audited Cycle 1 report/leaderboard and README result link within 24 hours of official publication.

PR D3: methods preprint source/package after the official report; SSRN submission remains a separate John-operated approval.

### 14.5 Issue-convergence checkpoints

PR I1: current issue-to-Bead-to-code evidence map and stale issue closures that require documentation changes.

PR I2: small non-ingestion backlog fixes that do not collide with launch tracks.

PR I3: deferred ingestion cleanup issues #67 and #97 after the acquisition checkpoint.

PR I4: release/branding/future-adapter cluster after first community acceptance.

PR I5: final acceptance audit and roadmap closure update.

## 15. Merge order and concurrency

P0 lands first because it establishes the graph and ownership map.

Immediately after P0, Tier-0 provider/publication terms, pinned LAB/evaluator characterization, native containment characterization, audience/claims work, and official source/eval tasks start in parallel.

P1 may land while acquisition continues, but it must not alter an active process underneath a running checkpoint.

O1 and O4 are parallel agent assignments inside the one W1 checkpoint branch, not two additional worktrees.

C-T0a is the first W2 implementation delivery after the narrow C0a evidence/governance checkpoint; C0b Codex characterization proceeds independently.

It depends only on provider/publication terms, the pinned LAB/evaluator seam, the native Claude containment/capability proof, and the narrow physical solver/private split required for the one task.

It does not depend on C1 through C6, hostile contributor-package intake, or issue #41.

C-T0b follows the capped paired run and independent artifact/claim review.

C1, C3N, and the broader #48 bridge are later native-path assignments inside W2, sequenced by the W2 integrator where they touch shared files.

C3M stays in the separately counted temporary W2-M only for a bounded landing pass; when W2-M is active, W3 implementation is inactive so W0 acquisition, W1 official eval, W2 native community, and W2-M mediated work remain the four concurrent implementation lanes.

Otherwise the steady-state lanes are W0 acquisition, W1 official eval, W2 native community, and W3 audience/issue/quality.

C1 depends on C0 and F-02 current-artifact characterization so its contracts reflect observed LAB and CLI seams.

C2 depends on the C1 score contract.

C4 depends on the C1 deliverable/evaluation contract; its upstream characterization is completed in C0 rather than hidden inside implementation.

C5 depends on the C1 core request/result identity and the profile-neutral native runtime slice; any mediated binding coordinates separately with C3M and cannot back-block clean-native activation.

C6a and C6b depend on C5 and proceed concurrently in separate counted worktrees after shared interfaces freeze.

C7 depends on C2, C3N, C4, and C6a; it produces the first contributor-grade row and does not wait for C3M or Codex.

C7 is renamed the Tier-1 contributor-grade Claude smoke and supersedes the preliminary Tier-0 evidence without erasing it.

C8 depends on C7 plus trusted validation/publication gates; it is the first #49 acceptance and does not wait for Codex.

C9 depends on C2, C3N, C4, and C6b; it may proceed alongside C7/C8 and does not wait for C3M.

C10 depends on the live feasibility evidence required to define matched arms and freezes the pilot before further comparative scores.

C11 depends on C10 and all selected live rows.

C12 depends on C8 and C9 so contributor docs reflect both accepted harness paths.

O2 depends on O1.

O3 depends on O2.

O8 depends on O1 through O5 and the required provider credentials.

O6 depends on the live acquisition reconciliation gate and exact-100 decision.

O7 depends on O6, the purchase decision, stage-specific Infisical folders, and downstream correctness tasks.

O9 depends on O7, O8, and all remaining canonical `5qd6.41` blockers.

I3 waits for the active acquisition checkpoint because #67 and #97 touch acquisition internals.

C9 may proceed alongside the Claude Tier-1 path once shared native interfaces freeze; it never delays Claude-first acceptance.

Distribution D0 starts immediately after P0.

D1 depends on the reviewed Tier-0 result, D2 on the official audited aggregate, and the preprint can be drafted with placeholders before either result exists.

No external LegalQuants response is required to keep engineering moving; the pilot freeze waits only for a predeclared input-window closure state, which may be feedback received, no response, or John declining to send.

## 16. Detailed work packages

The work packages below are implementation-sized units for Beads conversion.

Each package includes a purpose, owner lane, dependencies, deliverables, tests, and acceptance evidence.

Existing Beads are reused where named.

New Beads are successors or reconciliation tasks, not duplicate historical work.

The 140 package ledger is an obligation inventory, not permission to run 140 items at once.

Execution WIP follows the two labeled critical paths first; contributor-intake work follows Tier 0; `off-critical-path` work remains parked until the applicable launch or an explicit coordinator exception.

### P-01: Publish the retained dual-track roadmap

Lane: coordinator.

Priority: P0.

Dependencies: none.

Purpose: create one source of execution truth connecting the official run, community harness launch, and issue-convergence program.

Deliverables: this retained plan, a GitHub umbrella issue, and a linked top-level successor Bead.

Tests: Markdown link check, heading scan, dependency review, and fresh-eyes plan review.

Acceptance: the issue links the retained plan or plan PR, names both finish lines, lists the critical decisions, and links every relevant existing issue.

Acceptance: the Beads graph is cycle-free and contains ready parallel starts.

### P-02: Record the exact-100 Cycle 1 and reserve policy

Lane: W0 plus coordinator.

Priority: P0.

Dependencies: P-01.

Purpose: make the agreed exact-100 Cycle 1 objective immutable and remove the mismatch with the live blocking edges while acquisition continues toward the reserve.

Deliverables: signed-off decision record, projection policy, replacement rule, budget impact, and graph migration plan.

Tests: deterministic projection golden test and graph before/after validation.

Acceptance: the decision is recorded before any benchmark output exists.

Acceptance: the at-least-150 reserve no longer blocks `5qd6.39` and therefore no longer blocks `5qd6.41` transitively.

Acceptance: Cycle 1 remains exactly 100; the at-least-150 inventory is reserve and later-extension capacity and does not change the Cycle 1 matrix.

### P-03: Reconcile overlapping official-run records

Lane: W3.

Priority: P1.

Dependencies: P-01.

Purpose: make `5qd6.35` and `5qd6.41` canonical without discarding historical acceptance obligations.

Deliverables: dependency or evidence mapping for `ue7.32` and `ur6`.

Tests: live `bd show` and `bd dep cycles` validation.

Acceptance: no executor can mistake a legacy run record for a second official protocol.

Acceptance: old records close only when their acceptance is satisfied by canonical evidence.

### P-04: Establish issue terminal routes

Lane: W3.

Priority: P1.

Dependencies: P-01.

Purpose: ensure the long-term issue-cleanup goal is actionable without distracting from launches.

Deliverables: issue-to-Bead-to-PR-to-terminal-route matrix.

Tests: compare live `gh issue list`, live `bd list`, merged PRs, and code evidence.

Acceptance: all open issues have a current route, owner lane, dependencies, and milestone.

Conversion: P-04 and I-01 are one Bead and one deliverable, not duplicate planning work.

### P-05: Define checkpoint and refresh runbook

Lane: W3.

Priority: P1.

Dependencies: P-01.

Purpose: make version-control sequencing part of execution rather than an informal coordination detail.

Deliverables: concise worktree ownership, PR checkpoint, refresh, and stacked-branch instructions.

Tests: dry-run the protocol on a disposable branch or document existing verified commands.

Acceptance: every epic names its landing checkpoint and post-merge refresh dependency.

### P-06: Audit live graph after each planning mutation

Lane: coordinator.

Priority: P0.

Dependencies: P-01 for the immediate post-creation audit.

Purpose: prevent cycles, stale JSONL decisions, orphaned work, and misleading ready queues.

Deliverables: recorded live counts, cycle output, ready output, and fresh passive export if repo policy calls for it.

Tests: `bd dep cycles --json`, targeted `bd show`, and `bd ready --exclude-type epic`.

Acceptance: zero cycles, no unintended blocking of active acquisition, and every new non-epic task has a consumer or terminal deliverable.

Every later task that mutates the graph repeats these checks in its own acceptance criteria; P-06 is not an unbounded blocker that waits for every future graph writer.

### O-00: Reconcile the live acquisition source universe

Existing parent: `5qd6.73`.

Lane: coordinator plus W0 verifier.

Priority: P0.

Dependencies: P-01.

Purpose: derive the real target-gate blocker set from live tracker and artifact evidence before changing any launch dependency.

Deliverables: an inventory of every nonclosed `5qd6.73.*` child, with status and one of five dispositions: required source/recovery input, subsumed source, optional recovery, required operational hardening, or stale/superseded tracker state.

Tests: compare live `bd list --parent 5qd6.73`, source manifests, current checkpoints, exclusion ledgers, and merged implementation evidence; run a cycle check after any resulting status or dependency correction.

Acceptance: every nonclosed child has an evidence-linked disposition, every required lane is named as a blocker of O-05, and no active acquisition process is paused or status-mutated merely to simplify the graph.

### O-01: Complete July Case.dev enrichment

Existing Bead: `5qd6.73.34`.

Lane: W0.

Priority: P0.

Dependencies: existing live source and credential prerequisites.

Purpose: finish or formally exhaust the authenticated enrichment of the 3,244-candidate July source.

Deliverables: terminal per-candidate states, authenticated exclusions, checkpoint hashes, request accounting, and exact unresolved set.

Tests: resume from a copied checkpoint, duplicate suppression, config-identity refusal, and terminal-count reconciliation.

Acceptance: every candidate is successful, terminally excluded with reason, or explicitly pending with a machine-readable retry authority.

Acceptance: no downstream cohort claim treats the provisional prefix as the full source set.

### O-02: Screen terminal Case.dev successes through Firecrawl

Existing Bead: `5qd6.73.37`.

Lane: W0.

Priority: P0.

Dependencies: streaming successful completions from O-01.

Purpose: overlap screening with the long enrichment run without freezing a cohort prematurely.

Deliverables: provisional screening artifacts, source checkpoint identity, exclusions, and resumable pending queue.

Tests: append/resume identity, source-prefix mismatch refusal, later-completion merge, and duplicate candidate handling.

Acceptance: every screened result remains explicitly provisional until O-01 and target reconciliation complete.

Acceptance: later successful enrichments can be incorporated without rescreening prior terminal rows or losing provenance.

### O-03: Replay 22 operative-complaint exclusions

Existing Bead: `yr43.67`.

Lane: W0.

Priority: P0.

Dependencies: CourtListener rolling capacity and merged PR #198 behavior.

Purpose: recover cases excluded under the earlier complaint-resolution revision.

Deliverables: exact 22-case replay manifest, recovered complaint bindings, residual exclusions, and source evidence.

Tests: fixture reproduction of old exclusion, authenticated replay, capacity-stop resume, and ledger replacement semantics.

Acceptance: every one of the 22 cases has a current terminal recovery state.

Acceptance: successful recoveries replace rather than coexist ambiguously with obsolete exclusion records.

### O-04: Order complaint REST replay before Firecrawl fallback

Existing Beads: `yr43.67` and `5qd6.73.28`.

Lane: coordinator plus W0.

Priority: P0.

Dependencies: P-01.

Purpose: avoid credit-consuming fallback work for complaints recoverable through CourtListener REST.

Deliverables: live dependency edge and documented residual-handoff contract.

Tests: live graph cycle check and residual-set fixture.

Acceptance: before adding the dependency, the coordinator confirms that in-progress `5qd6.73.28` is not executing its final residual pass and records a safe checkpoint.

Acceptance: after the safe checkpoint, `5qd6.73.28` cannot start its final residual pass before `yr43.67` produces terminal results.

Acceptance: Firecrawl input equals the exact REST-unrecoverable residual set.

### O-05: Add immutable target-100 reconciliation gate

Existing parent: `5qd6.73`.

Lane: W0.

Priority: P0.

Dependencies: O-00, O-01, O-02, O-03, O-04, `5qd6.73.1`, `5qd6.73.23`, `5qd6.73.24`, `5qd6.73.28`, `5qd6.73.33`, and every additional required lane named by O-00.

Purpose: replace loose parent-child relationships with one auditable completion criterion.

Deliverables: reconciled candidate universe, terminal exclusion ledger, pending residual ledger, clean eligible pool, and immutable projection input.

Tests: count conservation, source-union uniqueness, ledger referential integrity, and replay determinism.

Acceptance: every source candidate occurs exactly once in the reconciled terminal or pending state model.

Acceptance: authenticated exclusions name the authority and evidence used.

Acceptance: the task closes only when reconciliation is complete and the clean eligible pool contains at least immutable `launch_case_count`, initially 100.

Acceptance: a shortfall produces a blocked state with the exact count and reactivation condition; it never closes the gate or makes projection ready.

Acceptance: every case eligible for projection has a canonical qualifying decision date on or after 2026-06-30.

### O-06: Freeze exact-100 projection policy

Lane: W0.

Priority: P0.

Dependencies: P-02, O-05, O-05A, O-08, and O-08A.

Purpose: choose the launch cohort without model-output influence.

Deliverables: projection policy artifact, exact sorted case IDs, deterministic rank-ordered replacement reserve, source-pool hash, disclosure/cost eligibility evidence hash, selection diagnostics, and replacement cutoff/authority.

Tests: deterministic rerun, reordered-input invariance, tie-breaking golden, and forbidden-field regression test.

Acceptance: rerunning the projector over identical source bytes produces identical exact-100 bytes.

Acceptance: the artifact can be verified without network or provider credentials.

Acceptance: the projection is frozen before packet exposure to benchmark models.

Acceptance: the projector rejects any case whose canonical qualifying decision date is before 2026-06-30 or cannot be proven.

Acceptance: the projection pool excludes cases lacking a supported disclosure decision or a feasible document plan under the precommitted cost policy.

### O-05A: Freeze the model universe and eligibility-anchor authority

Existing Bead: `5qd6.36`, using accepted model-registry and freeze evidence from `5qd6.24` where applicable.

Lane: W1 with W0 and John review.

Priority: P0.

Dependencies: intended Cycle 1 model registry evidence and the existing citation-check authority.

Purpose: bind the inclusive June 30, 2026 cutoff to its governing official-methods authority before projecting the cohort.

Deliverables: intended official model universe, release/deployment-date evidence, registry hash, derived inclusive eligibility anchor, and an explicit conclusion that the canonical cutoff is `2026-06-30`.

Tests: registry hash change, model addition/removal, release-date evidence change, derived-anchor golden, and projection invalidation.

Acceptance: if the cutoff derives from the latest first deployment in the evaluated model universe, the derivation is machine-verifiable and any model-universe change that changes the anchor invalidates projection.

Acceptance: if June 30 is instead a standalone methods decision, the artifact says so explicitly and records the approving authority because that is a material protocol choice.

### O-07: Continue at-least-150 reserve acquisition

Existing Bead: `5qd6.75`.

Lane: W0.

Priority: P1.

Dependencies: existing acquisition and purchase-planning prerequisites, but not O-18.

Purpose: build reserve inventory and enable a later extension without delaying Cycle 1.

Deliverables: at least 150 clean eligible cases or a bounded saturation report, plus an incremental production plan.

Tests: retained-cohort extension idempotency, non-overlap with frozen 100, and cost-plan reconciliation.

Acceptance: the reserve lane runs independently after the first 100 are ready.

Acceptance: no reserve result can alter Cycle 1 selection after model exposure.

### O-08: Produce supported authenticated disclosure reviews

Existing Bead: `5qd6.39.7`.

Lane: W0.

Priority: P0.

Dependencies: eligible clean candidates and stage-specific credential policy.

Purpose: replace any unsupported review artifact with the canonical authenticated producer required for projection and purchase decisions.

Deliverables: disclosure-review bundle, authority metadata, review decisions, hashes, and fail-closed errors.

Tests: authenticated fixture, missing-authority refusal, changed-input refusal, redaction, and package validation.

Acceptance: the projection and purchase decisions consume only supported review artifacts.

Acceptance: every cleared or excluded case has review authority and evidence.

### O-08A: Freeze preprojection disclosure and cost eligibility

Lane: W0.

Priority: P0.

Dependencies: O-05 and O-08.

Purpose: identify the disclosure-cleared candidate pool and estimate document feasibility before selecting the exact 100, without authorizing or making paid calls.

Deliverables: disclosure-clear candidate IDs, required-document inventory, free-versus-paid availability, conservative per-case reserve estimate, infeasible exclusions, and a hash-bound eligibility manifest.

Tests: no paid-call assertion, unsupported review refusal, missing-document classification, cap simulation, deterministic rerun, and candidate-count reconciliation.

Acceptance: the exact-100 projector receives only candidates whose disclosure and document plans are feasible under the frozen policy.

Acceptance: this task creates no purchase authorization and spends no provider credit.

### O-09: Make purchase decision and preserve cycle-wide cap

Existing Bead: `5qd6.37`.

Lane: W0.

Priority: P0.

Dependencies: O-06, O-08A, and verified provider fee policy.

Purpose: authorize exactly which missing documents for the selected 100 and explicitly approved replacement reserve may be purchased within the approved Cycle 1 budget.

Deliverables: purchase plan, canonical cycle ledger identity, reservations, approvals, and no-purchase exclusions.

Tests: cap boundary, concurrent reservation denial, crash after submission, unknown outcome reconciliation, and zero automatic retry for charge-bearing calls.

Acceptance: projected and reserved spend cannot exceed the immutable cycle cap.

Acceptance: ambiguous paid outcomes remain reserved until provider-side evidence resolves them.

Acceptance: the plan contains no broader credential or unapproved purchase path.

Acceptance: no purchase row falls outside the selected 100 or the hash-bound replacement reserve authorized by the projection policy.

### O-10: Create parser and labeling Infisical folders

Existing Bead: `5qd6.76`.

Lane: John.

Priority: P0.

Dependencies: human Infisical UI access.

Purpose: create least-privilege stage folders without teaching the pipeline to use broader secrets.

Deliverables: dedicated parser path, dedicated labeling path, access verification, and no printed secret values.

Tests: metadata-only path probe and one bounded stage authentication smoke.

Acceptance: both currently missing paths stop returning 404.

Acceptance: parser credentials cannot be used for labeling and labeling credentials cannot be used for parser or official eval.

### O-11: Land operator CLI and runbook conformance repair

Existing Bead: `5qd6.39.11`.

Lane: W0 or W3, assigned to one owner only.

Priority: P0.

Dependencies: current downstream CLI contract.

Purpose: ensure the operator can execute the documented first-100 pass exactly as tested.

Deliverables: corrected commands, arguments, artifact names, and error guidance.

Tests: command help snapshots, provider-free runbook command execution, and stale-command rejection.

Acceptance: every runbook command resolves and its output feeds the next documented stage.

Acceptance: no step depends on undocumented manual file surgery.

### O-12: Build an honest provider-free exact-100 downstream rehearsal

Existing Bead: `5qd6.39.6`.

Lane: W0 with W3 review.

Priority: P0.

Dependencies: O-11 and stable downstream schemas.

Purpose: exercise assembly through packet readiness without external credentials or charges.

Deliverables: deterministic 100-case fixture projection, synthetic or approved fixture documents, expected ledgers, labels, packets, and audit results.

Tests: one operator command or scripted sequence from clean temp root, forced interruption/resume, deliberate exclusion, failed audit, and exact artifact comparison.

Acceptance: the rehearsal proves the complete downstream control flow, not semantic quality of synthetic legal facts.

Acceptance: the test fails if a stage silently skips work or accepts an incomplete predecessor.

### O-13: Assemble, refresh, and disclosure-clear exact 100

Existing parent: `5qd6.39`.

Lane: W0.

Priority: P0.

Dependencies: O-06, O-08, O-11, and O-12.

Purpose: turn the frozen projection into canonical downstream inputs.

Deliverables: assembled cohort, refresh manifest, current disclosure decisions, replacement events if any, summary, and exclusions.

Tests: source-hash verification, refresh policy, replacement cutoff, count conservation, and completed-snapshot gate.

Acceptance: exactly 100 cases proceed or the stage fails closed with a frozen shortfall.

Acceptance: every input points to a completed acquisition snapshot.

### O-14: Purchase and download approved documents

Existing parent: `5qd6.39`.

Lane: W0.

Priority: P0.

Dependencies: O-09 and O-13.

Purpose: complete the bounded missing-document set and materialize all approved source bytes.

Deliverables: purchase ledger, provider receipts, downloaded files, recovery manifest, hashes, and exclusions.

Tests: atomic download, redirect denial, byte ceiling, corrupted existing-file refusal, resume, and unknown purchase recovery.

Acceptance: every canonical document is validated and hash-bound before parsing.

Acceptance: actual and reserved spend reconcile to the approved cap.

### O-15: Parse and normalize the corpus

Existing parent: `5qd6.39`.

Lane: W0.

Priority: P0.

Dependencies: O-10 and O-14.

Purpose: produce complete bounded text artifacts from the acquired documents.

Deliverables: parser inputs, normalized text, OCR or fallback decisions, per-document provenance, failures, and cost journal.

Tests: parser environment allowlist, missing secret refusal, malformed document, oversized output, partial checkpoint resume, and deterministic normalization.

Acceptance: every required document has an accepted parse or an exclusion/replacement decision.

Acceptance: parser subprocesses receive only the dedicated stage environment.

### O-16: Unitize and adjudicate exact 100

Existing parent: `5qd6.39`.

Lane: W0.

Priority: P0.

Dependencies: O-15.

Purpose: construct forecast units and resolve ambiguous claim/defendant mappings before labels freeze.

Deliverables: unit records, model/judge attempt journal, adjudication queue, lawyer resolutions, and audit trail.

Tests: journal resume, disagreement route, duplicate unit rejection, human override authority, and cost reservation.

Acceptance: every retained case has a complete, internally consistent unit set.

Acceptance: unresolved adjudication prevents freeze.

### O-17: Label and audit exact 100

Existing parent: `5qd6.39`.

Lane: W0 plus John or lawyer reviewer.

Priority: P0.

Dependencies: O-10 and O-16.

Purpose: create outcomes and measured label-quality evidence without circular benchmark-model judging.

Deliverables: judge registry, label records, raw resolution strata, human audit sample, error-rate report, routing report, and exclusions.

Tests: exact-model disjointness, cycle-wide sampling, observed-stratum coverage, finite-population behavior, null-rate failure, threshold breach, and journal resume.

Acceptance: the predeclared audit plan was frozen before sampling.

Acceptance: all observed strata are sampled according to policy and the release gate passes.

Acceptance: disjointness language accurately distinguishes exact-model from provider-family independence.

### O-18: Build packets and final corpus ledgers

Existing parent: `5qd6.39`.

Lane: W0.

Priority: P0.

Dependencies: O-13 through O-17.

Purpose: produce the exact model-visible materials and final corpus evidence for official freeze.

Deliverables: packet manifest, model-visible packet bytes, contamination/leakage audit, final summary, final exclusion ledger, adjudication closure, and corpus-readiness report.

Tests: docket cutoff, post-decision leakage, path safety, packet hash reproducibility, exact count, and disclosure guardrails.

Acceptance: exactly 100 packets are ready and every packet hash is stable across a clean rebuild.

Acceptance: no unresolved purchase, parse, unit, label, audit, or disclosure state remains.

Acceptance: every packet's canonical qualifying decision date is on or after the frozen inclusive `2026-06-30` anchor and the packet-visible material passes the forecast-time cutoff check.

### O-19: Freeze shard schedule and dispatch provenance

Existing Beads: `5qd6.25` and successors.

Lane: W1.

Priority: P0.

Dependencies: current protocol schemas, independent of corpus bytes.

Purpose: make partial shard dispatches valid against one full-cycle freeze.

Deliverables: shard schedule schema, execution policy fields, dispatch-provenance validation, version migrations, and fixtures.

Tests: declared shard acceptance, undeclared shard rejection, duplicate shard rejection, model/ablation mismatch, and freeze-hash mismatch.

Acceptance: each legal shard can be validated without weakening full-cycle identity.

Acceptance: old full-matrix behavior remains readable where required.

### O-20: Implement shard-only workflow and concurrency identity

Existing Bead family: `5qd6.25` through `5qd6.29`.

Lane: W1.

Priority: P0.

Dependencies: O-19.

Purpose: prevent partial shards from aggregating and prevent GitHub Actions pending-run replacement.

Deliverables: shard-only input, shard-aware concurrency key or proven queue policy, gated aggregate job, and actionlint assertions.

Tests: workflow expression tests, eight-shard scheduling simulation, shard-only aggregate suppression, and invalid input failure.

Acceptance: dispatching all declared shards cannot silently cancel pending peers.

Acceptance: a shard cannot publish or sync an official partial report.

### O-21: Implement immutable shard finalizer receipts

Existing Bead family: `5qd6.25` through `5qd6.29`.

Lane: W1.

Priority: P0.

Dependencies: O-20.

Purpose: bind each successful shard attempt to the exact cells and object versions it commits.

Deliverables: finalizer job, receipt schema, immutable receipt key, fresh-versus-resumed cell list, and object commitment.

Tests: missing cell, extra cell, stale object, overwrite attempt, failed matrix, resumed cell, and receipt hash tamper.

Acceptance: a receipt is written only after all expected cells verify.

Acceptance: reruns create new receipts rather than overwriting prior evidence.

### O-22: Implement accepted-attempt fan-in

Existing Bead family: `5qd6.25` through `5qd6.29`.

Lane: W1.

Priority: P0.

Dependencies: O-21.

Purpose: make multi-attempt shard recovery deterministic and auditable.

Deliverables: receipt discovery, accepted-attempt map, object-version verification, exact shard coverage, and verify-only mode.

Tests: one receipt per shard, multiple receipts without map, invalid map, stale receipt, object mismatch, missing shard, duplicate shard, and extra cell.

Acceptance: fan-in refuses ambiguous reruns until a hash-bound selection map exists.

Acceptance: only cells committed by accepted receipts enter the official aggregate.

### O-23: Complete cycle-wide spend and attempt accounting

Existing Bead: `5qd6.28` and related accounting work.

Lane: W1.

Priority: P0.

Dependencies: frozen model and retry policies.

Purpose: enforce one provider/account cap across shards and preprocessing calls.

Deliverables: transactional reservations, attempt journal, settlement, unknown-state handling, circuit breaker, and report.

Tests: concurrent reservation race, 429 retry ownership, timeout after send, malformed usage, rerun adoption, cap exhaustion, and crash recovery.

Acceptance: no combination of shards can jointly exceed the approved account cap through independent local budgets.

Acceptance: every billable attempt is represented even when no usable result is produced.

### O-24: Complete provider and environment isolation

Existing Beads: `5qd6.32`, `5qd6.33`, and `5qd6.34` where applicable.

Lane: W1.

Priority: P0.

Dependencies: official credential policy.

Purpose: keep provider credentials, artifacts, and dispatch identities scoped to the intended stage and shard.

Deliverables: allowlisted environments, OIDC or bounded credential path, provenance fields, and denial tests.

Tests: wrong provider, missing credential, credential cross-stage use, artifact path traversal, and secret redaction.

Acceptance: each shard receives only the credential and artifacts it needs.

Acceptance: secrets and private paths are absent from receipts and public run cards.

### O-25: Run official workflow smoke

Existing Bead: `5qd6.35`.

Lane: W1 plus John for required approvals.

Priority: P0.

Dependencies: O-19 through O-24 and required credentials.

Purpose: prove the real workflow, receipt, resume, budget, and verify-only path before the official freeze.

Deliverables: smoke freeze, workflow run links, receipts, ledger, verify-only report, failure drill, and remediation evidence.

Tests: one successful shard, intentional interrupted or failed attempt, resume or accepted-attempt recovery, and no publication.

Acceptance: smoke evidence satisfies the canonical rehearsal obligations mapped from `ue7.32`.

Acceptance: no unresolved P0 defect remains in the official path.

### O-25A: Revalidate the eligibility anchor and served-model registry

Existing Bead: `5qd6.96`.

Lane: W1 and John.

Priority: P0 within 24 hours before dispatch.

Dependencies: O-05A and the frozen official registry.

Purpose: prevent schedule delay or served-alias drift from silently invalidating the official design.

Deliverables: current registry/source hashes, served alias/version evidence, inclusive June 30 anchor confirmation for every selected case, `model_universe_frozen_at`, `registry_cut_at`, intended `dispatch_at`, `anchor_to_dispatch_days`, and `registry_cut_to_dispatch_days`.

Tests: registry/freeze equality, served-model probe or authoritative evidence, selected-case anchor audit, and no-output-before-reprojection assertion.

Acceptance: the Bead cannot close more than 24 hours before dispatch; any in-universe drift produces an explicit John continue, replace/reproject-before-output, or defer decision.

Acceptance: a newly released model outside the frozen universe affects market-freshness disclosure but never enters Cycle 1 silently.

Acceptance: the evidence records the residual possibility of an undetectable weight roll behind an unchanged alias/model string and avoids an unsupported immutable-revision claim.

### O-26: Freeze and dispatch official Cycle 1

Existing Bead: `5qd6.41`.

Lane: John with W0 and W1 support.

Priority: P0 at launch gate.

Dependencies: O-18, O-25, O-25A, `5qd6.36`, and every remaining live blocker on `5qd6.41`.

Purpose: execute the first official benchmark without output-informed intervention.

Deliverables: immutable freeze, eight declared dispatches or the frozen schedule, successful receipts, accepted-attempt map if needed, and fan-in verification.

Tests: pre-dispatch freeze verification rejects O-25A evidence older than 24 hours, live run monitoring, receipt completeness, cap reconciliation, and verify-only fan-in before aggregate.

Acceptance: every frozen cell is present exactly once under an accepted receipt.

Acceptance: no unplanned model, case, ablation, or retry enters the run.

Acceptance: dispatch cannot start with O-25A evidence older than 24 hours; if the intended dispatch slips beyond that window, O-25A is reopened or regenerated and reverified.

### O-27: Audit, aggregate, and publish official Cycle 1

Existing Bead: `5qd6.41`; `5qd6.40` is a separately parked post-cycle diagnostics/publication enhancement and does not block the first report.

Lane: W1, W3, and John.

Priority: P0.

Dependencies: O-26.

Purpose: turn verified cells into the canonical audited data artifacts, aggregate, and run card that the separate D-02 human-facing report renders.

Deliverables: official aggregate, confidence intervals, calibration outputs, refusal/invalid rates, realized outcome prevalence, any valid frozen pre-run baseline or human reference, the unranked constant-0.5 reference when no empirical baseline exists, run card, methods disclosures, audit evidence, canonical machine-readable artifacts, and publication handoff record.

Tests: exact Cartesian aggregate, extra/missing cell rejection, reconstruction from hashes, publication guardrails, static render, and independent result audit.

Acceptance: the report makes only claims supported by the Cycle 1 baseline and audit design.

Acceptance: if no valid frozen historical baseline corpus exists, the report says `no empirical predictive baseline and no Brier skill claim for Cycle 1`; a same-sample prevalence constant is labeled post-hoc oracle context, never a forecast baseline.

Acceptance: `ur6` and overlapping legacy run records can be evidence-closed or linked to this run.

### F-01: Amend the modular-monolith boundary ADR

Lane: W3.

Priority: P1.

Dependencies: P-01.

Purpose: make the official/community separation explicit without a premature monorepo migration.

Deliverables: an amendment or superseding revision to accepted `docs/adr/0001-community-multiharness-scope.md`, with current violations, target dependency directions, package-split triggers, compatibility policy, and ownership map.

Tests: import graph scan and review against actual modules.

Acceptance: the ADR explains why one project is retained now and what evidence would trigger a split.

Acceptance: it forbids community-to-official promotion and official imports of community orchestration.

### F-02: Characterize current multiharness artifacts

Lane: W2.

Priority: P0.

Dependencies: closed epic `054`.

Purpose: preserve existing fixture behavior while adding real score semantics.

Deliverables: golden fixtures for current run summaries, submission packages, aggregate rows, static reports, and migration expectations.

Tests: read/rewrite equivalence, unknown-version refusal, and current release smoke.

Acceptance: new schema work cannot silently break already-valid fixture packages.

### F-02A: Define core run and execution-receipt contracts

Lane: W2.

Priority: P0.

Dependencies: F-02, R-00A, and R-00B for observed CLI identity requirements.

Purpose: provide neutral execution contracts that runtime and auth services can implement without depending on publication summaries.

Deliverables: versioned `RunSpec`, auth-category identity, retry/repeat identity, `resume_identity`, `ExecutionReceipt`, requested/actual executable and model identities, runtime-policy reference, usage/cost/timing, deliverable reference, and validators.

Tests: changed task/config/policy/auth/executable/model, failed execution, partial receipt, unresolved model, resume mismatch, and unsupported version.

Acceptance: runtime/auth packages depend only on neutral contracts and never import community submission/publication envelopes.

### F-03: Build the canonical task materializer

Lane: W2.

Priority: P0.

Dependencies: F-02, H-00, and I-06A's decoded-path and recursive-key hardening.

Purpose: give native LAB, Claude Code, Codex, and future adapters identical verified task bytes.

Deliverables: typed materialization request, materialization manifest, safe copy/projection implementation, and validator.

Tests: traversal, symlink escape, special file, overlap, hash mismatch, oversize, reordered source listing, and deterministic output.

Acceptance: all adapters consume only a materialized task root created by this service.

Acceptance: no public artifact exposes host absolute paths.

### F-04: Build the canonical deliverable contract

Lane: W2.

Priority: P0.

Dependencies: F-03 and H-00.

Purpose: normalize harness outputs before evaluation.

Deliverables: schema, expected-slot rules, output discovery, hash manifest, migration hooks, and validator.

Tests: missing deliverable, wrong media type, symlink, executable, special file, oversized file, extra output, and tamper.

Acceptance: evaluation receives only a validated deliverable artifact and content root.

### F-04A: Build canonical evaluation specifications and receipts

Lane: W2.

Priority: P0.

Dependencies: F-04 and H-00.

Purpose: create the trust anchor between a closed deliverable and normalized score without mixing evaluator execution into task or score identity.

Deliverables: versioned `EvaluationSpec`, `EvaluationReceipt`, evaluator runtime-policy hash, private-material commitment, requested/resolved judge identities, raw private-result hash, usage/cost/timing, issuer identity, and validator.

Tests: changed deliverable, changed rubric, changed private-material commitment, unresolved judge, invalid issuer, tampered raw-result hash, failed evaluation, and unsupported version.

Acceptance: every score references exactly one valid evaluation receipt.

Acceptance: a fresh stochastic judge call creates a new receipt and repeat index rather than verifying or overwriting the first call.

### F-05: Build the canonical score artifact

Lane: W2.

Priority: P0.

Dependencies: F-02, F-04A, and H-00.

Purpose: make community comparisons carry actual grader-backed metrics instead of status-only metadata.

Deliverables: versioned score schema, typed `MetricDefinition` references, deterministic normalized observations derived from an evaluation receipt, failure semantics, and validator.

Tests: null versus zero, incompatible metric definitions, receipt mismatch, suite mismatch, missing rubric coverage, precision/rounding drift, tampered score, and unsupported version.

Acceptance: a score cannot be published without a validated chain to task, deliverable, evaluator, and run identities.

### F-05A: Define efficiency and accounting observations

Lane: W2 with W3 audience review.

Priority: P0 before contract freeze.

Dependencies: F-02A, F-04A, and F-05.

Purpose: make cost, tokens, wall-clock, attempts, completion, and coverage co-equal public comparison dimensions without duplicating them into the score artifact.

Deliverables: typed solve/evaluation/total usage fields; provider-reported, price-sheet-estimated, and subscription-unallocable cost bases; currency and pricing snapshot identity; solver/evaluator/task/experiment timing; queue and retry accounting; coverage joins; and public display rules.

Tests: unavailable usage, provider report versus estimate, subscription-unallocable cost, cached-token double counting, reasoning-token availability, retry inclusion, parallel summed-time versus wall-clock, currency/basis mismatch, incompatible cost ratio, and one-task variance suppression.

Acceptance: unknown values are null with reasons, subscription is never reported as zero cost, and the public view can render score, coverage, cost, tokens, time, attempts, and failures as peer columns from authoritative receipts.

Acceptance: no default score-per-dollar composite or cross-currency ratio is created.

### F-06: Extend run summaries with artifact references

Lane: W2 integrator.

Priority: P0.

Dependencies: R-06, F-04, F-04A, F-05, and F-05A.

Purpose: connect run specification, execution receipt, deliverable, evaluation receipt, and scoring through content hashes.

Deliverables: new `CommunityRunSummary` version referencing every applicable artifact, legacy reader, writer, and status/failure mapping.

Tests: legacy fixture read, new fixture round-trip, missing artifact, hash mismatch, and partial failure.

Acceptance: public aggregation never scrapes adapter logs for results.

### F-07: Propagate metrics through community packaging

Lane: W2 integrator.

Priority: P0.

Dependencies: F-05, F-05A, and F-06.

Purpose: make validated metrics visible in shards, submissions, aggregates, and static reports.

Deliverables: package schema updates, validator rules, aggregate metric tables, coverage/failure tables, and static render changes.

Tests: full package E2E, incompatible group refusal, partial coverage, failure denominator, and legacy fixture handling.

Acceptance: the public report displays task-level and aggregate scores, selected/solved/evaluated coverage, usage, cost basis, tokens, wall-clock, attempts, and failures with exact compatibility labels.

Acceptance: the report never combines incompatible suites or evaluator revisions.

### F-08: Add comparison and repeat policy

Lane: W2 with W3 review.

Priority: P1.

Dependencies: F-05, F-05A, and F-07.

Purpose: separate one-task plumbing evidence from interpretable pilot conclusions.

Deliverables: paired comparison functions, repeat index, prespecification artifact, coverage policy, and uncertainty rules.

Tests: paired tasks, missing arm, unequal repeats, failure inclusion, incompatible model, and one-task warning.

Acceptance: one-task output is explicitly labeled smoke-only.

Acceptance: causal harness language is enabled only for exact matched compatibility groups.

### F-09: Enforce official/community import boundaries

Lane: W3.

Priority: P1.

Dependencies: F-01A and stable F-03 through F-07 APIs.

Purpose: prevent future feature growth from collapsing the conceptual separation.

Deliverables: import rules or architecture tests, allowed shared primitive list, and violation remediation.

Tests: deliberately forbidden import fixtures and full package import smoke.

Acceptance: official publication cannot import the community runner or aggregate.

Acceptance: community code reaches official data only through explicit public task projections.

### F-01A: Baseline and enforce the import budget

Lane: W3.

Priority: P0 before new community contracts land.

Dependencies: F-01.

Purpose: snapshot named legacy official/community reverse-import exceptions and reject new violations immediately while later remediation proceeds.

Deliverables: current import graph, allowlisted legacy exceptions with owners, CI architecture rule, and failure guidance.

Tests: one allowed legacy exception, one new forbidden official-to-community import, one forbidden community-to-privileged-ingestion import, and normal package import.

Acceptance: no new reverse dependency can merge after the foundation starts.

### F-10: Cover adapter example paths in CI

Lane: W3.

Priority: P1.

Dependencies: F-02.

Purpose: ensure changes under `examples/adapters/**` trigger the relevant validation workflows.

Deliverables: isolated workflow path-filter patch and regression assertion.

Tests: actionlint and path-filter event fixtures or inspection.

Acceptance: adapter example changes cannot merge without community validation.

Acceptance: workflow-file push uses the secure-gate reviewed path.

### R-00A: Prove Claude Code native outer-containment feasibility

Lane: W2 Agent C1 with security review.

Priority: P0 and no-spend.

Dependencies: E-01 and the pinned/probed Claude distribution.

Purpose: determine whether the characteristic Claude Code harness can run LAB tasks with its native loop and local tools preserved inside a whole-process outer boundary.

Deliverables: exact 2.1.210-versus-installed-2.1.211 pin decision; executable/help/hash evidence; proof that native filesystem/shell tools remain available inside the disposable workspace; proof that hooks, plugins, skills, settings, browser/web bypasses, and unrelated MCP servers are absent; deliverable production; auth/publication risk record; and the outer-boundary gap list.

Tests: real local no-provider-call configuration probe, native read/write/shell probes inside the disposable workspace, denied host/private paths, denied ambient settings and web/browser surfaces, output write, process cleanup, and capability identity.

Acceptance: the result records whether the profile preserves enough stock behavior to call `claude-code-clean-native`, with every deliberate deviation disclosed.

Acceptance: failure stops the native claim or chooses a narrower explicit profile; it never silently substitutes the MCP-mediated arm.

### R-00B: Prove Codex CLI native-sandbox and outer-containment feasibility

Lane: W2 Agent C2 with security review.

Priority: P0 and no-spend.

Dependencies: E-01 and the pinned/probed Codex distribution.

Purpose: determine whether the characteristic Codex CLI harness can run LAB tasks with its native loop, shell/filesystem tools, and sandbox preserved inside an outer disposable boundary.

Deliverables: executable/help/hash evidence; proof that native tools and the selected Codex sandbox remain the harness treatment; proof that ambient rules, skills, config, web/MCP bypasses, repo/home/auth files are absent; deliverable production; auth/publication risk record; and the outer-boundary gap list.

Tests: real local no-provider-call configuration probe, native read/write/shell probes inside the disposable workspace, denied host/private paths, ambient config canaries, output write, process cleanup, and capability identity.

Acceptance: the result records whether the profile preserves enough stock behavior to call `codex-cli-clean-native`, with every deliberate deviation disclosed.

Acceptance: failure stops the native claim or chooses a narrower explicit profile; it never silently substitutes the MCP-mediated arm.

### R-00C: Build the contributor-grade native whole-process boundary

Lane: W2 integrator with security review.

Priority: P1 after Tier 0 and P0 for contributor intake.

Dependencies: R-00A, R-00B, R-05, R-10, and the narrow Tier-0 observations.

Purpose: turn the one-task trusted-operator containment proof into a reusable native-harness boundary safe enough for accepted contributor workflows.

Deliverables: non-root disposable sandbox launcher, read-only root/input, output/scratch mounts, resource limits, provider-only egress policy, web/browser denial, isolated HOME/XDG/session state, credential projection policy, output sealing, process cleanup, and separate evaluator launch.

Tests: host home/repo/auth/socket/cloud-metadata denial, general-network denial, evaluator-private denial, native tool success inside scope, output sealing, timeout descendants, malicious public input, and public allowlist scan.

Acceptance: native tools remain the harness treatment while the whole process cannot reach undeclared host or evaluator surfaces.

Acceptance: unsupported provider endpoint or credential behavior fails closed and records the narrower reproducibility claim.

### R-01: Finish the hardened host-owned tool runtime

Existing GitHub issue: #41.

Existing Bead: `2dnr`.

Lane: W2 or its existing dedicated branch, one owner at a time.

Priority: P1 as a secondary mediated-profile path; active implementation may continue independently.

Dependencies: the already-landed versioned tool protocol.

Purpose: turn the recorded sandbox plan into an enforced Docker or Podman execution boundary.

Deliverables: backend abstraction, digest-pinned image enforcement, network-disabled runtime, read-only root, bounded tmpfs, non-root UID, dropped capabilities, no-new-privileges, resource limits, and cleanup.

Tests: missing backend, mutable tag, network attempt, home read, socket access, root escalation, resource exhaustion, timeout, nonzero exit, and orphan process/container cleanup.

Acceptance: adapters declaring the `mcp_mediated` tool profile cannot run without this boundary.

Acceptance: the runtime never silently falls back to host tool execution.

### R-02: Bind tool receipts to resume identity

Existing GitHub issue: #41.

Lane: W2.

Priority: P1 for the secondary mediated contributor path.

Dependencies: R-01.

Purpose: resume only tool work proven identical to the current request and policy.

Deliverables: sanitized execution receipt, request/result hashes, policy hash, image digest, task/run identity, resource summary, and successful-completion marker.

Tests: changed task, changed image, changed policy, changed arguments, stale receipt, failed receipt, missing output, and tampered output.

Acceptance: only a matching successful receipt suppresses repeated execution.

Acceptance: receipt contents are safe for community package validation.

### R-03: Implement process-group cancellation and cleanup

Lane: W2.

Priority: P1 after Tier 0 and P0 when Tier-1 contributor activation begins.

Dependencies: current command adapter characterization.

Purpose: prevent timeouts or cancellation from leaving child provider/tool processes alive.

Deliverables: process-group launch, graceful termination window, forced kill, descendant cleanup, and failure classification.

Tests: child process tree, ignored termination signal, partial stdout, output-file lock, timeout, and user cancellation.

Acceptance: no adapter or container process survives a timed-out row.

Acceptance: the run summary distinguishes timeout, cancellation, cleanup failure, and adapter failure.

### R-04: Define explicit authentication profiles

Lane: W2 with security review.

Priority: P1 after Tier 0 and P0 when Tier-1 contributor activation begins.

Dependencies: F-02A.

Purpose: support contributor-owned local CLI use without ambiguous or unsafe credential discovery.

Deliverables: typed auth profile, explicit selection, public category, environment allowlist, unsupported-mode errors, and documentation.

Tests: no auth, wrong profile, forbidden fallback, secret-shaped environment, account metadata redaction, and profile mismatch on resume.

Acceptance: `fixture_none`, `explicit_api_key`, and `local_cli_subscription` are distinct identities.

Acceptance: a run never switches profile because one credential source happens to fail.

### R-05: Build minimal host environment projection

Lane: W2.

Priority: P1 after Tier 0 and P0 when Tier-1 contributor activation begins.

Dependencies: R-04.

Purpose: prevent unrelated host configuration, hooks, plugins, skills, and credentials from affecting a run.

Deliverables: allowlisted environment builder, isolated HOME/XDG/config roots, explicit executable path, locale/timezone policy, and sanitized current directory.

Tests: hostile environment variables, project-local settings, user hooks, unapproved MCP servers, PATH shadowing, locale drift, and home canary.

Acceptance: only declared environment fields reach the provider process.

Acceptance: adapter identity changes when any behavior-affecting allowed configuration changes.

### R-06: Build shared local CLI execution service

Lane: W2 integrator.

Priority: P1 after Tier 0 and P0 when Tier-1 contributor activation begins.

Dependencies: R-03, R-04, R-05, and F-02A.

Purpose: give Claude Code and Codex identical lifecycle, framing, redaction, and resume semantics.

Deliverables: typed request/result API, process execution, JSON/JSONL framing, stdout/stderr separation, timeout, cancellation, transcript policy, and run identity.

Tests: invalid JSON, mixed stdout, truncated line, large output, nonzero exit, timeout, cancellation, partial result, changed executable, and resume mismatch.

Acceptance: adapter-specific modules do not reimplement process lifecycle or public redaction.

Acceptance: the service does not inherit the repository cwd implicitly.

### R-07: Add executable capability probes

Lane: W2.

Priority: P1 after Tier 0 and P0 when Tier-1 contributor activation begins.

Dependencies: R-06.

Purpose: fail closed when installed CLI flags or output contracts drift.

Deliverables: version probe, help/feature probe, structured-output handshake, executable hash, supported-auth modes, and capability identity.

Tests: missing executable, unexpected version, missing flag, changed framing, incompatible output, and fake executable fixtures.

Acceptance: no paid task begins until the selected adapter's required capabilities pass.

Acceptance: live run provenance contains the probe result hash.

### R-08: Centralize transcript and secret redaction

Lane: W2 with security review.

Priority: P1 after Tier 0 and P0 when Tier-1 contributor activation begins.

Dependencies: R-06.

Purpose: keep useful diagnostics private while preventing public leakage.

Deliverables: structured event classifier, private log root, public error projection, secret detector, path scrubber, and artifact allowlist.

Tests: bearer tokens, API keys, OAuth-shaped values, account IDs, email, absolute paths, source text, hidden grader text, and malicious adapter output.

Acceptance: public packages are allowlist-built rather than denylist-cleaned copies of workspaces.

Acceptance: raw transcripts never enter public artifacts by default.

### R-09: Add hostile MCP-mediated runtime canaries

Lane: W2 plus W3 review.

Priority: P1 for the secondary mediated contributor path.

Dependencies: R-01, R-02, R-05, and R-08.

Purpose: prove the claimed boundary against deliberate exfiltration attempts.

Deliverables: canary home file, canary credential, network endpoint, socket, repository file, and expected denial receipt.

Tests: attempt to read each canary, resolve DNS, make outbound connection, access Docker socket, traverse symlink, and persist a child process.

Acceptance: all canary attempts fail and no canary value appears in stdout, stderr, receipts, or public packages.

Acceptance: the negative-control job cleans up every container and process.

### R-09A: Add hostile native whole-process E2E

Lane: W2 plus W3 review.

Priority: P1 after Tier 0 and P0 for contributor intake.

Dependencies: R-00C, R-08, R-10, and I-06B.

Purpose: prove the contributor-grade `clean_native` boundary without substituting the issue #41 tool runtime.

Deliverables: native Claude and Codex boundary fixtures, solver/evaluator canaries, malicious public inputs, provider-egress controls, output sealing evidence, and sanitized denial receipts.

Tests: native in-scope tool success plus host, credential, network, socket, metadata, evaluator-private, persistence, and process-escape failures.

Acceptance: the native profile is eligible for Tier-1 contributor intake only after every applicable canary and clean-package scan passes.

### R-10: Separate solver inputs from evaluator-private material

Lane: W2.

Priority: P1 after Tier 0 and P0 when Tier-1 contributor activation begins; E-00B owns the deliberately narrow Tier-0 split.

Dependencies: F-03 and F-04.

Purpose: prevent the solver harness from seeing hidden rubrics, reference answers, judge prompts, or evaluator-only files.

Deliverables: public solver-input manifest, private evaluator-input manifest, disjoint materialization roots, access rules, and leakage check.

Tests: hidden rubric canary, reference-answer canary, symlink escape, evaluator-root mount refusal, and public package scan.

Acceptance: the clean-native provider CLI and its native tool descendants can access only the solver-input/output/scratch roots declared for that whole-process boundary; the mediated provider host and issue #41 tool container obey their separately declared roots.

Acceptance: the evaluator receives the validated deliverable plus evaluator-private materials only after solve completion.

### H-01: Pin and mirror the Harvey LAB compatibility target

Existing GitHub issues: #48 and #196.

Lane: W2.

Priority: P0.

Dependencies: license and retention policy from closed #40.

Purpose: replace moving-upstream assumptions with one reproducible compatibility target.

Deliverables: upstream commit, repository and license credit, local checkout/source hash, immutable source URL or approved checkout rule for publication, and compatibility fixture.

Tests: checkout hash mismatch, missing license, changed CLI help, and unavailable immutable source.

Acceptance: adapter capability identity binds the exact upstream revision.

Acceptance: public text does not imply affiliation.

Acceptance: the initial compatibility target is Harvey LAB commit `73feb91d63d53b1a44151d99329779c4defcdb72`; changing it requires a pre-spend comment or amendment on #196 with the replacement hash and rationale.

### H-02: Characterize real LAB run and evaluate commands

Existing GitHub issue: #48.

Lane: W2.

Priority: P0.

Dependencies: H-01.

Purpose: replace obsolete `--lab-root` and `--output-dir` assumptions with the actual upstream workflow.

Deliverables: command contract, task/model/run ID mapping, expected files, exit behavior, and interface-drift fixtures.

Tests: pinned no-credential probes, fake checkout, missing command, changed flag, and invalid task ID.

Acceptance: the bridge uses only commands observed at the pinned revision.

### H-00: Characterize LAB evaluator feasibility before freezing contracts

Existing GitHub issues: #48 and #196.

Lane: W2.

Priority: P0 and blocks final community contract design.

Dependencies: H-01 and H-02.

Purpose: observe the real pinned evaluator seam before defining canonical task, deliverable, evaluation, and score contracts.

Deliverables: exact solver-visible files; native deliverable bytes/layout; evaluator-private files; external-deliverable acceptance behavior; judge/provider requirements; criterion, weighting, rounding, missingness, and aggregate semantics; and a no-credential characterization fixture.

Tests: native fixture solve/evaluate discovery, externally supplied deliverable probe, hidden-material inventory, command trace, and source-level confirmation of scoring semantics.

Acceptance: the plan selects one feasible path: direct pinned evaluator support, a narrow hash-bound compatibility overlay, a separately implemented evaluator adapter reproducing the pinned contract, or plumbing-only external runs with no comparative score claim.

Acceptance: F-03 through F-05 are frozen from observed fixtures rather than guessed upstream behavior.

### H-03: Implement deterministic LAB task projection

Existing GitHub issue: #48.

Lane: W2.

Priority: P0.

Dependencies: F-03, H-01, and R-10.

Purpose: map canonical tasks onto LAB inputs without exposing evaluator-private material to solvers.

Deliverables: LAB loader revision, solver/evaluator manifest split, task ID mapping, source hashes, and output contract.

Tests: real pinned checkout fixture, hidden material denial, task reorder, duplicate ID, and hash drift.

Acceptance: native and external harness arms receive byte-identical solver-visible task inputs.

### H-04: Implement safe LAB output discovery

Existing GitHub issue: #48.

Lane: W2.

Priority: P0.

Dependencies: F-04 and H-02.

Purpose: discover deliverables only within approved run roots under actual upstream naming.

Deliverables: deterministic run directory mapping, output locator, canonical deliverable conversion, and drift errors.

Tests: nested path, unexpected output, symlink, multiple candidates, missing output, and stale prior run.

Acceptance: stale or ambiguous outputs cannot be scored as the current run.

### H-05: Invoke the LAB evaluator separately

Existing GitHub issue: #48.

Lane: W2.

Priority: P0.

Dependencies: F-04A, F-05, H-00, H-02, H-04, and R-10.

Purpose: apply one pinned grader path to native and external deliverables.

Deliverables: evaluation request, private material projection, separate evaluator runtime policy, evaluator invocation, raw private result, canonical evaluation receipt, deterministic score normalization, and cost approval.

Tests: evaluator failure, judge auth failure, malformed score, changed rubric, changed deliverable, timeout, cost-cap refusal, malicious PDF/DOCX/archive, embedded macro/script, parser resource exhaustion, and ambient credential access.

Acceptance: evaluation does not rerun the solver.

Acceptance: all published scores derive from the same pinned evaluator for a compatibility group.

Acceptance: evaluator execution receives read-only deliverable and evaluator-private roots, no solver workspace/home/repository/socket/ambient credential, bounded resources and outputs, no executable document macros/scripts, and host-mediated judge calls when provider credentials are required.

### H-06: Recompute or verify submitted scores in trusted CI

Lane: W2 plus W3.

Priority: P0 for comparative publication.

Dependencies: H-05 and F-07.

Purpose: avoid trusting contributor-authored score numbers merely because their hashes are internally consistent, while treating stochastic judge repeats as new measurements rather than verification.

Deliverables: project-operated evaluator path, protected workflow or other concrete receipt issuer identity, signed/attested evaluation receipt, immutable deliverable retrieval, deterministic normalization recomputation, and mismatch handling.

Tests: forged score, altered deliverable, altered grader revision, invalid issuer, altered raw-result hash, unavailable private grader, immutable URL mismatch, stochastic repeat misclassified as verification, and valid resubmission.

Acceptance: comparative site publication requires a trusted score verification result.

Acceptance: CI verifies the project-authorized receipt and deterministically recomputes score normalization from its committed raw result.

Acceptance: a new LLM-judge invocation creates a new evaluation receipt/repeat and is never treated as proof that the first stochastic result was correct.

Acceptance: the receipt issuer is concretely named as a protected workflow/OIDC identity, project signing authority, or equally specific reviewed mechanism before live evaluation.

### H-07: Implement native LAB comparison arm

Existing GitHub issue: #48.

Lane: W2.

Priority: P1.

Dependencies: H-03 through H-05 for implementation; comparative publication additionally depends on H-06.

Purpose: produce the thin native harness baseline used for matched comparisons.

Deliverables: native run adapter, canonical deliverable, canonical score, capability identity, and offline fake.

Tests: pinned checkout, no credentials, model mismatch, output discovery, evaluator reuse, and resume.

Acceptance: native and external rows share task/evaluator compatibility identity when configured with the same exact model.

### H-08: Freeze low-cost smoke task fixture

Existing GitHub issue: #196.

Lane: W2.

Priority: P0.

Dependencies: H-01 and H-03.

Purpose: preserve a cheap, meaningful, deterministic end-to-end acceptance target.

Deliverables: task `employment-labor/identify-issues-in-counterparty-motion-brief`, source hash, eight-source-document input manifest, one-`.docx` deliverable expectation, 23-criterion rubric identity, cost estimate, and no-tool/tool requirements.

Tests: fixture materialization, hidden-material split, selection hash, and upstream drift.

Acceptance: the task remains the same across native, Claude, and Codex smoke attempts unless a new prespecification supersedes it.

Acceptance: any replacement task, upstream revision, or Claude Code version is recorded on #196 before spend with the new hashes and rationale.

### A-01: Specify the generic local CLI adapter manifest

Lane: W2 integrator.

Priority: P0.

Dependencies: F-02A, F-03, F-04, and R-06.

Purpose: avoid duplicating task, auth, execution, and result identity semantics in two adapters.

Deliverables: manifest schema, capability fields, executable probe reference, supported suite/task modes, auth profiles, model identity, tool policy, output parser, and public fields.

Tests: unknown capability, incompatible suite, missing parser, unsupported auth, and manifest hash change.

Acceptance: Claude Code and Codex differ only in adapter-specific commands and event normalization where possible.

### A-02: Build fake Claude Code executable

Lane: W2 Agent C1.

Priority: P0.

Dependencies: A-01.

Purpose: exercise every integration path without credentials, network, or paid calls.

Deliverables: deterministic fake executable with success, invalid JSON, timeout, nonzero, partial output, model drift, tool request, and secret-leak modes.

Tests: all modes through the shared runner and package validator.

Acceptance: CI can test the full adapter lifecycle without detecting a real Claude installation.

### A-03: Implement Claude Code capability probe

Existing GitHub issue: #196.

Lane: W2 Agent C1.

Priority: P0.

Dependencies: R-07 and A-02.

Purpose: bind the exact noninteractive Claude interface before spend.

Deliverables: version/hash probe, required-flag verification, structured event handshake, model-resolution check, and supported-auth report.

Tests: current real binary probe as opt-in, fake version drift, missing flag, unexpected event, and wrong model.

Acceptance: unsupported Claude versions fail before task materialization or provider call.

### A-04A: Implement the offline Claude Code adapter core

Existing GitHub issue: #196.

Lane: W2 Agent C1.

Priority: P0.

Dependencies: A-01 through A-03, R-06, and F-04.

Purpose: implement the command builder, capability/event parser, typed execution integration, fake-executable path, and fixture deliverable while live tool/auth/evaluator gates continue in parallel.

Deliverables: offline manifest, command builder, event normalizer, fake execution, fixture deliverable, failure mapping, and conformance tests.

Tests: fake success, malformed stream, timeout, cancellation, nonzero exit, partial result, model drift, resume mismatch, and fixture output discovery.

Acceptance: the offline adapter core passes without Docker, provider credentials, a live LAB checkout, or a real Claude invocation.

### A-04: Implement the native-contained Claude Code headless adapter

Existing GitHub issue: #196.

Lane: W2 Agent C1.

Priority: P0.

Dependencies: A-04A, R-00A, R-00C, R-03 through R-08, R-09A, R-10, H-03 through H-05, and A-11.

Purpose: run the characteristic Claude Code harness over LAB tasks with its native loop and local tools preserved inside the contributor-grade whole-process boundary.

Deliverables: `claude-code-clean-native` manifest, headless command builder, frozen native-tool policy, outer-boundary launcher integration, event normalizer, deliverable discovery, result summary, and docs.

Tests: fake end-to-end, no-tool handshake, native in-scope tool success, out-of-scope host/web/private-root denial, timeout, model mismatch, auth unavailable, output sealing, resume, and public redaction.

Acceptance: adapter identity is distinct from Claude Agent SDK.

Acceptance: native tool calls remain inside the declared outer workspace and no task MCP server replaces them.

Acceptance: published issue #196 baseline uses explicit API-key auth unless its acceptance criteria are amended.

### A-05: Build fake Codex executable

Lane: W2 Agent C2.

Priority: P0.

Dependencies: A-01.

Purpose: test the Codex adapter fully offline.

Deliverables: deterministic fake JSONL executable with success, invalid event, timeout, nonzero, partial result, model drift, tool request, and secret-leak modes.

Tests: all modes through the shared runner and package validator.

Acceptance: CI does not require a real Codex installation or subscription.

### A-06: Implement Codex capability probe

Lane: W2 Agent C2.

Priority: P0.

Dependencies: R-07 and A-05.

Purpose: bind the installed noninteractive Codex interface before spend.

Deliverables: version/hash probe, required-flag verification, JSONL handshake, model-resolution check, sandbox capability check, and supported-auth report.

Tests: current real binary probe as opt-in, fake version drift, missing flag, unexpected event, wrong model, and forbidden config discovery.

Acceptance: unsupported Codex versions fail before task materialization or provider call.

### A-07A: Implement the offline Codex CLI adapter core

Lane: W2 Agent C2.

Priority: P0.

Dependencies: I-11, A-01, A-05, A-06, R-06, and F-04.

Purpose: implement the command builder, capability/event parser, typed execution integration, fake-executable path, and fixture deliverable while live tool/auth/evaluator gates continue in parallel.

Deliverables: offline manifest, ephemeral command builder, event normalizer, fake execution, fixture deliverable, failure mapping, and conformance tests.

Tests: fake success, malformed JSONL, timeout, cancellation, nonzero exit, partial result, model drift, resume mismatch, and fixture output discovery.

Acceptance: the offline adapter core passes without Docker, provider credentials, a live LAB checkout, or a real Codex invocation.

### A-07: Implement the native-contained Codex CLI adapter

Lane: W2 Agent C2.

Priority: P0.

Dependencies: A-07A, R-00B, R-00C, R-03 through R-08, R-09A, R-10, H-03 through H-05, and A-12.

Purpose: run Codex as a distinct community harness over LAB tasks with its native loop, tools, and sandbox preserved inside the contributor-grade outer boundary.

Deliverables: `codex-cli-clean-native` manifest, ephemeral command builder, frozen native sandbox/tool policy, outer-boundary launcher integration, event normalizer, deliverable discovery, result summary, and docs.

Tests: fake end-to-end, no-tool handshake, live tool negative control, timeout, model mismatch, auth unavailable, config suppression, resume, and public redaction.

Acceptance: adapter identity is distinct from OpenAI Responses API.

Acceptance: native tool calls remain inside the declared outer workspace and no task MCP server replaces them.

### A-08: Register adapters without central CLI branching

Lane: W2 integrator.

Priority: P1.

Dependencies: A-04A and A-07A; live capability exposure additionally depends on A-04 and A-07.

Purpose: expose both adapters through a stable manifest/registry seam.

Deliverables: registry entries, list/probe commands, CLI wiring, help text, and examples.

Tests: adapter listing, unknown adapter, unsupported suite, help snapshots, and duplicate identity.

Acceptance: adding a future adapter does not require copying a large root CLI block.

### A-09: Add local subscription contributor profile

Lane: W2 with security and policy review.

Priority: P1.

Dependencies: E-01, R-04, R-05, and R-08.

Purpose: implement the generic contributor-owned local CLI subscription profile without presenting those runs as portable API baselines.

Deliverables: explicit opt-in flag or profile, provider-specific eligibility notes, auth projection, attestation text, public label, and failure guidance.

Tests: unsupported provider, missing login, forbidden token copy, full-home request, profile mismatch, redaction, and package validation.

Acceptance: the profile uses the CLI's supported login in place and never exports durable auth material.

Acceptance: the package clearly labels the result as contributor-owned local subscription execution.

### A-10: Add explicit API-key published profile

Lane: W2.

Priority: P1.

Dependencies: E-01, R-04, R-05, and R-08.

Purpose: implement the generic explicit API-key profile used by reproducible published baselines.

Deliverables: allowlisted credential environment, key presence check without value logging, provider-call policy, spend cap, and publication attestation.

Tests: missing key, wrong key variable, extra secret, redaction, cap refusal, and package validation.

Acceptance: the exact credential projection boundary and any inheritance into native descendants are canary-tested and recorded; a profile that exposes credentials more broadly than its threat model permits fails closed rather than claiming parent-only isolation.

Acceptance: no credential reaches any public package; the MCP-mediated profile keeps it out of the issue #41 tool container, while clean-native eligibility follows the separately verified whole-process threat model.

### A-11: Bind auth profiles to Claude Code

Lane: W2 Agent C1.

Priority: P0 for Claude live activation.

Dependencies: A-04A, A-09, and A-10.

Purpose: map the generic auth profiles onto Claude Code's supported login and explicit credential surfaces without fallback.

Deliverables: profile-to-command/environment binding, auth-category probe, unsupported-mode error, redaction, and #196 API-key selection.

Tests: subscription login, explicit API key, missing auth, forbidden fallback, full-home denial, account metadata redaction, and resume-profile mismatch.

Acceptance: the #196 published baseline selects the explicit API-key profile unless #196 is amended before spend.

Acceptance: any local subscription row is separately labeled and never exports Claude credential state.

### A-12: Bind auth profiles to Codex CLI

Lane: W2 Agent C2.

Priority: P0 for Codex live activation.

Dependencies: A-07A, A-09, and A-10.

Purpose: map the generic auth profiles onto Codex's supported ChatGPT-sign-in and single-run API credential surfaces without fallback.

Deliverables: profile-to-command/environment binding, `codex login status` category probe without account data, unsupported-mode error, redaction, and contributor labels.

Tests: ChatGPT sign-in category, explicit API key, missing auth, forbidden fallback, `CODEX_HOME`/auth-file denial, account metadata redaction, and resume-profile mismatch.

Acceptance: Codex runs record only the auth category and never package or copy `auth.json`, keyring contents, access tokens, or personal configuration.

### A-13: Add optional MCP-mediated decomposition profiles

Lane: W2 after the native Tier-1 path.

Priority: P2 post-launch unless the pilot prespecifies a planner-versus-toolset question.

Dependencies: R-01, R-02, R-09, the applicable offline adapter core, and the applicable auth binding.

Purpose: retain the issue #41 tool-mediated design as a scientifically separate arm rather than redefining the native Claude Code or Codex treatment.

Deliverables: `claude-code-mcp-mediated` and, only if useful, `codex-cli-mcp-mediated` manifests; strict bridge configuration; distinct capability/tool-policy identity; and comparison guidance.

Tests: native tool fallback denial, receipt-bound tool calls, network-disabled tool container, identity separation from clean-native rows, and package labels.

Acceptance: the mediated row can decompose planner versus toolset effects but never substitutes for or is pooled with a clean-native row.

### E-01: Verify provider terms and supported automation modes

Lane: W3.

Priority: P0 before a contributed subscription row.

Dependencies: P-01 and current official provider documentation.

Purpose: distinguish supported local CLI subscription use from API entitlement and unsupported automation, including whether benchmark results generated under each profile may be published.

Deliverables: dated primary-source links, permitted profile matrix, publication-rights matrix, unresolved policy questions, and contributor attestation language.

Tests: documentation review by a second agent and capability check against the installed binaries.

Acceptance: the record states whether and how current OpenAI primary sources support ChatGPT sign-in for local Codex execution and API-key auth for programmatic workflows; changed, conditional, or ambiguous terms narrow or block that profile rather than being forced into a favorable conclusion.

Acceptance: the record states whether and how current Anthropic primary sources include Claude Code in eligible subscriptions and permit the intended automation/publication surface; changed, conditional, or ambiguous terms narrow or block that profile.

Acceptance: no provider statement is generalized beyond its documented product surface.

Acceptance: the record separately states whether operator-run and contributor-run benchmark scores, cost/usage summaries, and configuration metadata may be published from API-key and subscription-tier execution; ambiguity stops publication under that profile.

### E-00A: Govern the native-tools Tier-0 experiment

Existing GitHub issue: #196.

Lane: W2 with W3 methods/audience review.

Priority: P0 critical path.

Dependencies: E-01 only.

Purpose: amend issue #196 into Phase A preliminary native paired smoke and Phase B reproducible contributor acceptance, and freeze the intended scientific treatment and forbidden claims before Tier-0 implementation or spend while the native-feasibility and LAB-characterization probes run in parallel.

Deliverables: accepted issue amendment; `claude-code-clean-native` primary and `claude-code-mcp-mediated` secondary identities; CLI/LAB pin rules and decision deadline pending the parallel probes; Tier-0 threat model; publication permissions; exact minimal credibility gates; target date; and forbidden claims.

Tests: independent methods/security review and a compatibility-key preview that treats native harness prompt/loop/tool differences as the treatment rather than a nuisance mismatch.

Acceptance: no issue text or plan still defines MCP substitution as the primary Claude Code arm.

Acceptance: the permanent public label is `Preliminary — one task pair, operator-run, not independently reproducible`, and #49 remains unsatisfied.

### E-00B: Build and freeze the narrow Tier-0 paired path

Lane: W2 Agents C1 and C3 under the integrator's file map.

Priority: P0 critical path.

Dependencies: E-00A and the pinned LAB evaluator seam.

Purpose: stage only the one pinned LAB task's solver-visible bytes, prove evaluator-private exclusion, preserve native Claude tools in the disposable outer boundary, and freeze the paid-run specification.

Deliverables: hash-bound read-only input projection, empty output/scratch roots, solver/private inventory and canaries, safe output locator, native Claude command/capability record, native LAB command, separate evaluator invocation, exact model/settings/order/caps/timeout/claims, public artifact allowlist, arm-opaque evaluator IDs and evaluation-order policy, and provider-free dry run.

Tests: byte identity across arms, no LAB checkout/rubric/answer/evaluator mount in the solver boundary, output sealing, host/private-path denial, web/browser denial, secret/path/grader canary scan, evaluator-after-solver ordering, arm-label absence from judge input, identical evaluator context, deterministic randomized evaluation order, and dry-run failure retention.

Acceptance: the specification is committed before the first paid solver or judge call and no output-selective retry path exists.

### E-00C: Execute, review, and publish the preliminary paired smoke

Lane: W2 operator with independent W3 review.

Priority: P0 critical path.

Dependencies: E-00B and explicit bounded-spend approval.

Purpose: answer Jamie's immediate question quickly without representing the result as contributor-grade or general evidence.

Deliverables: all solver attempts, sealed deliverables, separately issued evaluator results, arm-opaque evaluation map, score/coverage, solve/evaluation tokens and cost basis, solver/evaluator/experiment wall-clock, completion/failure status, exact configuration/hashes, private raw streams, public allowlisted package, redaction scan, and issue #196 evidence.

Tests: frozen order/cap adherence, exact task bytes, exact model parity check, sealed-before-evaluate proof, evaluator blindness to harness labels where feasible, prespecified evaluation order, no credential/account/path/transcript/grader leakage, independent arithmetic/claim review, and permanent artifact hashes.

Acceptance: exact parity permits only the observed matched paired difference for this pinned task/run; any model/provider/settings/resource-policy mismatch forces system-bundle language, and output features that defeat arm blinding are disclosed.

Acceptance: the result does not close #49, and the later Tier-1 path supersedes rather than erases it.

### E-00D: Freeze the nonblocking Codex Tier-0 addendum

Lane: W2 Agent C2 with C3 evaluator review.

Priority: P0 parallel critical path that cannot delay E-00B/E-00C.

Dependencies: E-00B's provider-free solver/private split and R-00B; it does not wait for E-00C or the Claude result.

Purpose: reuse the pinned task projection and evaluator seam to answer the separate near-term Codex-native question without making Claude wait for Codex feasibility.

Deliverables: pinned Codex binary/hash and clean-install native capability inventory; exact Codex and native-thin-LAB arms where model parity is feasible; model/provider/settings/resource/stopping/order/evaluator addendum; arm-opaque evaluation plan; budget; claims; and provider-free dry run.

Tests: native tool success, ambient-config/private-root/network denials, byte identity, evaluator-private exclusion, model-parity decision, child-credential exposure canary, deterministic order, cap simulation, and no paid call before the addendum commit.

Acceptance: the addendum is frozen before Codex or paired-native spend, discloses every clean-install deviation, and creates no blocker edge to E-00C.

### E-00E: Execute, review, and publish the Codex Tier-0 follow-on

Lane: W2 Agent C2 as operator with independent W3 review.

Priority: P0 immediately after E-00D, target within two days of the Claude Tier-0 result.

Dependencies: E-00D and explicit bounded-spend approval.

Purpose: produce the first scored Codex-native configuration promptly while keeping it scientifically and operationally separate from the Claude-first Jamie result.

Deliverables: all Codex and applicable paired-native attempts; sealed deliverables; arm-opaque evaluator receipts; score/coverage; cost basis, tokens, solver/evaluator/experiment wall-clock, attempts/failures; exact hashes/configuration; reviewed allowlisted public package; and README/writeup addendum evidence.

Tests: frozen-spec/order/cap adherence, exact task bytes, parity/key computation, sealed-before-evaluate proof, evaluator blindness where feasible, secret/account/path/grader scan, arithmetic/claim review, and permanent artifact hashes.

Acceptance: every public surface carries `Preliminary — one task pair, operator-run, not independently reproducible`; a matching key permits only the observed paired difference for this task/run, mismatch forces system-bundle language, and no generalized Claude-versus-Codex or harness-superiority claim is made.

Acceptance: E-00E may inform the later common Tier-1 interfaces, but it neither closes #49 nor delays the Claude Tier-0 terminal.

### E-02: Run private no-tool credential handshakes

Lane: W2.

Priority: P1.

Dependencies: R-04 through R-08, A-03, A-06, A-11, and A-12.

Purpose: prove local CLI invocation, selected auth profile, model resolution, event parsing, redaction, and cleanup before live task tools exist.

Deliverables: private Claude handshake receipt, private Codex handshake receipt, versions, hashes, resolved model data where available, and sanitized summaries.

Tests: one bounded prompt per CLI, timeout, no session persistence, environment canary, config canary, and log scan.

Acceptance: no task or evaluator score is produced.

Acceptance: a successful handshake is explicitly not counted as #49 or a comparative result.

### E-03: Freeze the Tier-1 contributor-grade one-task smoke design

Lane: W2 with W3 review.

Priority: P0.

Dependencies: H-08, F-08, and E-01.

Purpose: incorporate Tier-0 observations while preventing execution convenience from changing the contributor-grade task or claims after results appear.

Deliverables: exact task, arms, model identities, auth profiles, evaluator/judge, tool policy, execution order, budget, timeout, and smoke-only claim language.

Tests: prespecification schema validation and compatibility-key preview.

Acceptance: the artifact is committed before the first paid solver or evaluator call.

Acceptance: unmatched arms are labeled system-bundle plumbing results.

### E-04: Run the Tier-1 contributor-grade Claude Code one-task smoke

Existing GitHub issue: #196.

Lane: W2 with explicit operator approval.

Priority: P0 after safety gates.

Dependencies: R-00C, R-03 through R-08, R-09A, R-10, H-01 through H-06, A-04, A-11, E-00C, and E-03.

Purpose: prove the reproducible native-contained external LAB harness path end to end after the preliminary observation.

Deliverables: execution receipt, canonical deliverable, trusted score artifact, private logs, public summary, cost report, and validation report.

Tests: live boundary canaries, expected deliverable, grader recomputation, package scan, and clean-site rebuild.

Acceptance: the run is real, non-fixture, bounded, and uses the pinned task and policies.

Acceptance: published issue #196 evidence satisfies its API-key criterion unless a reviewed issue amendment says otherwise.

### E-03A: Govern first-adapter fallback only if Claude is externally blocked

Lane: coordinator and John.

Priority: P0 only when activated.

Dependencies: documented external Claude blocker after all in-scope fixes and supported auth paths are exhausted.

Purpose: avoid encoding an unimplementable OR dependency for #49 while preserving a deliberate fallback to Codex if Claude cannot proceed for an external reason.

Deliverables: blocker evidence, decision, claim impact, and a reviewed dependency change from E-04 to E-05 for E-07.

Tests: live graph cycle check and #49 acceptance revalidation.

Acceptance: the default graph remains Claude-first; fallback requires an explicit recorded decision rather than silently accepting whichever result appears first.

### E-05: Run the Tier-1 contributor-grade Codex one-task smoke

Lane: W2 with explicit operator approval.

Priority: P0 after safety gates.

Dependencies: R-00C, R-03 through R-08, R-09A, R-10, H-01 through H-06, A-07, A-12, and E-03.

Purpose: prove the same community pipeline with the second locally installed harness.

Deliverables: execution receipt, canonical deliverable, trusted score artifact, private logs, public summary, cost report, and validation report.

Tests: live boundary canaries, expected deliverable, grader recomputation, package scan, and clean-site rebuild.

Acceptance: the run is real, non-fixture, bounded, and uses the pinned task and policies.

Acceptance: the row is named as a Codex-plus-model system configuration.

### E-06: Produce a matched native-LAB observation and compatibility proof

Existing GitHub issues: #48 and #49.

Lane: W2 with explicit operator approval.

Priority: P1 for a matched-pair observation; it cannot by itself support a generalized harness-effect claim.

Dependencies: H-07, E-03, and compatible model/auth access.

Purpose: create the thin native arm and prove compatibility for a paired external-harness observation.

Deliverables: native execution receipt, deliverable, trusted score, cost report, and compatibility proof.

Tests: byte-identical solver input, exact model match, common evaluator, and compatibility-key equality.

Acceptance: exact compatibility permits only the observed paired difference for the pinned task/run; if parity cannot be established, the native row is published separately as a system bundle, and generalized effect language always waits for E-08/E-09 pilot evidence.

### E-07: Satisfy first real community acceptance

Existing GitHub issue: #49.

Lane: W2 and W3.

Priority: P0.

Dependencies: E-04 plus all #49 artifact/runtime prerequisites by default; E-03A may deliberately rewire this single edge to E-05 if Claude is externally blocked.

Purpose: reuse the same paid smoke as adapter acceptance and community intake evidence.

Deliverables: PR-ready community package, immutable public-safe artifact reference, attestations, validation logs, aggregate rebuild, static report, and privacy audit.

Tests: clean clone package validation, trusted score verification, immutable URL hash, undeclared file denial, secret scan, and static render.

Acceptance: no duplicated paid run is performed merely to satisfy two issues.

Acceptance: issue #49 links the accepted submission and evidence.

### E-08: Freeze a small stratified pilot

Lane: W2 with methods review.

Priority: P1.

Dependencies: successful E-04 through E-06 plumbing and F-08.

Purpose: move from the separate one-task Tier-0 smoke to an interpretable comparison without post-pilot-score task selection.

Deliverables: task strata, exact task IDs, selection hash, arms, exact model matching rules, randomized order, repeat count, failure policy, coverage floor, uncertainty method, budget, and stopping rule.

Tests: deterministic selection, balance diagnostics, order-generation golden, and budget simulation.

Acceptance: the pilot task/arm selection and design are committed before any stratified-pilot score is observed; any Tier-0-informed change is disclosed with the proposed shard, feedback, accepted/rejected rationale, and final frozen-spec diff.

Acceptance: any unmatched Claude-versus-Codex analysis is labeled system-bundle comparison.

### E-09: Execute the stratified pilot

Lane: W2 with operator approvals.

Priority: P1.

Dependencies: E-08 and all relevant runtime/adapters.

Purpose: produce the first informative community comparison dataset.

Deliverables: all receipts, deliverables, trusted score artifacts, coverage/failure table, paired differences where valid, cost/latency summary, and public package.

Tests: run-order adherence, cap enforcement, resume identity, repeated-task identity, clean regrade, and clean site rebuild.

Acceptance: stopping and omission rules match the prespecification.

Acceptance: every failure remains in the denominator according to policy.

### E-10: Document contributor-owned execution

Lane: W3 with W2 review.

Priority: P1.

Dependencies: E-07 and A-09/A-10.

Purpose: let community members reproduce and contribute without copying John's machine-specific setup.

Deliverables: installation prerequisites, pinned checkout steps, auth-profile decision guide, capability probe, run command, validation command, package command, PR instructions, cost warning, privacy warning, and troubleshooting.

Tests: fresh machine or clean user-profile walkthrough with fixture mode; opt-in live walkthrough by a second operator if available.

Acceptance: fixture validation works without credentials.

Acceptance: live instructions never ask contributors to upload or copy credential stores.

Acceptance: documentation distinguishes local subscription rows from API-key published baselines.

### E-11: Add Community Harness Comparisons submission policy

Lane: W3.

Priority: P1.

Dependencies: F-07, H-06, and E-07.

Purpose: define what the project will accept, display, compare, quarantine, or reject.

Deliverables: accepted suites, auth categories, score verification, artifact retention, privacy, compatibility, claim taxonomy, revocation, correction, and withdrawal policies.

Tests: policy examples for valid, incompatible, unverifiable, revoked, and malicious submissions.

Acceptance: maintainers can make consistent decisions without examining private credentials or transcripts.

### E-12: Add later public LegalForecast community projection

Lane: W2 and W3.

Priority: P2 after both launches.

Dependencies: official disclosure decision, stable community contracts, and explicit public packet policy.

Purpose: allow community harness execution against a publishable LegalForecast task surface without touching official private artifacts.

Deliverables: public task projection, licensing/disclosure record, loader, expected deliverable, scoring adapter, and cross-namespace tests.

Tests: leakage audit, namespace isolation, official promotion denial, task hash reproducibility, and package validation.

Acceptance: this work does not block the Harvey LAB pilot or official Cycle 1.

### D-00: Freeze the audience, claims, and publication calendar

Lane: W3 Agent D2.

Priority: P0 and immediately ready after PLAN-MR.

Dependencies: P-01.

Purpose: make audience and time-to-result first-class launch constraints without allowing communications to weaken methods.

Deliverables: practitioner, AI-research, LegalQuants, and contributor audiences; canonical calls to action/URLs; preliminary, reproducible, and official claim tiers; required evidence and forbidden language for each tier; non-affiliation text; owners; publication approvals; and the dated calendar in section 21.

Tests: fresh-eyes audience/methods review and consistency checks across README, report templates, issue #196, and the roadmap.

Acceptance: every public surface names its evidence tier and cannot silently upgrade a preliminary or system-bundle result.

### D-01: Build the human-facing Cycle 1 report shell

Lane: W3 Agent D0.

Priority: P0 in parallel with acquisition.

Dependencies: D-00.

Purpose: build the page that practitioners and researchers will actually read before official results exist.

Deliverables: fixture-backed static report/leaderboard with headline micro-Brier and intervals, calibration, refusal/invalid rates, realized prevalence and allowed baseline context, accounting, one-paragraph contamination story, limitations, and METHODS/reproduce/audit links.

Tests: fixture arithmetic, official/community visual separation, static render, responsive layout, accessibility, link integrity, and publication guardrails.

Acceptance: audit detail is one click deeper and the first screen is interpretable to a skimming reader.

### D-02: Populate, audit, and publish the Cycle 1 report

Lane: W3 Agent D0 with independent methods/arithmetic review.

Priority: P0 after the official aggregate.

Dependencies: D-01 and O-27.

Purpose: render and publish the human-facing official result promptly from O-27's canonical audited artifacts rather than creating a second aggregate owner.

Deliverables: populated report, permanent URL and artifact hash, claims/arithmetic audit, publication record, and README link refresh within 24 hours.

Tests: reconstruction from official hashes, aggregate/report equality, baseline-language guard, static render, link check, and independent sign-off.

Acceptance: the page states whether a valid frozen empirical baseline exists and never claims Brier skill when it does not.

### D-03: Publish the preliminary harness-comparison writeup

Lane: W3 Agent D1 with W2 evidence review.

Priority: P0 critical path for audience value.

Dependencies: D-00 and E-00C.

Purpose: answer the timely Claude-Code-versus-thin-LAB question in an honest, useful, short form.

Deliverables: template prepared before results; exact task/model/harness/native-tool/evaluator/judge/auth settings; what matched and did not; score and coverage; solve/evaluation cost, tokens, time, attempts, and failures; artifact links; limitations; and README link refresh.

Tests: comparison values reconstruct from receipts, every unmatched variable is disclosed, no one-task variance/significance language appears, secret/path scan passes, and independent claim review passes.

Acceptance: every surface says `Preliminary — one task pair, operator-run, not independently reproducible` and reports at most the observed paired difference for this pinned task/run when the corrected matched key passes; generalized `harness effect`, `performs better`, or superiority language waits for the prespecified pilot and supported uncertainty.

### D-04A: Draft the LegalQuants engagement loop

Lane: W3 Agent D2.

Priority: P0.

Dependencies: D-00.

Purpose: turn LegalQuants from a passive audience into a potential pilot-design participant without implying partnership or surrendering preregistration control.

Deliverables: immediate draft reply to Jamie explaining that the intended primary arm preserves native Claude Code tools pending feasibility; invitation to comment before stratified-pilot task/arm selection is finalized and before any stratified-pilot score; preliminary-result follow-up draft; non-affiliation language; and a predeclared feedback-window close date.

Tests: methods/non-affiliation review and confirmation that no unpublished confidential artifact or unsupported result appears.

Acceptance: this task drafts only and performs no external send.

### D-04B: Approve/send or decline the LegalQuants messages

Lane: John.

Priority: P0 human checkpoint.

Dependencies: D-04A; the result follow-up additionally waits for D-03.

Purpose: preserve human authority for external communications while preventing an external response from blocking the pilot indefinitely.

Deliverables: John approval/send or explicit decline, permalink if sent, feedback record, and window closure as feedback received, no response, or declined send.

Tests: verify the sent text and permalink against the approved draft without collecting private account information.

Acceptance: pilot design may consume feedback only before stratified-pilot selection/freeze and scores, waits for the declared window state rather than for a response to exist, and archives the proposed shard, feedback, accepted/rejected rationale, final frozen specification, and any change informed by the separate Tier-0 result.

### D-05: Draft and package the methods preprint

Lane: W3 Agent D1 with methods review.

Priority: P1; drafting begins immediately.

Dependencies: draft depends on D-00; final package depends only on D-02.

Purpose: convert the strong `docs/METHODS.md` foundation and audited results into a research artifact legible to legal and AI-research audiences.

Deliverables: 6–10 page manuscript covering design, contamination resistance, Cycle 1 methods/results, limitations, and reproducibility; citation audit; SSRN package; optional arXiv package; and a separately labeled harness-comparison appendix only if validated evidence is ready without delaying the MTD paper.

Tests: source-to-claim citation audit, table reconstruction, leakage/publication guardrails, render check, and independent methods review.

Acceptance: SSRN submission requires a separate John authorship/publication approval; arXiv never blocks SSRN or the report.

### D-06: Turn README into the landing page

Lane: W3 Agent D1.

Priority: P0.

Dependencies: D-00.

Purpose: make the repository's first screen communicate the benchmark, current status/result, contamination claim, official/community distinction, and next action before contributor mechanics.

Deliverables: concise first screen, current-result/status component, official versus community explanation, METHODS/audit/reproduce links, and update hooks owned by D-02/D-03.

Tests: link check, render/readability review, stale-result fixture, non-affiliation wording, and contributor path discoverability.

Acceptance: no permanent `coming soon` claim remains after a result publishes, and each result link updates within 24 hours.

### I-01: Inventory every open GitHub issue

Lane: W3.

Priority: P1.

Dependencies: P-04.

Purpose: replace chronological backlog pressure with a dependency-aware terminal map.

Deliverables: issue number, title, current truth, related Bead, related PR/code, route, milestone, owner lane, and closure evidence.

Tests: live `gh issue list`, issue body/comments, related PR state, and targeted code verification.

Acceptance: the inventory covers all 17 issues open at the planning snapshot and any newly opened roadmap issue.

### I-02: Reconcile community umbrella #10

Lane: W3.

Priority: P1.

Dependencies: I-01.

Purpose: update stale subtask expectations without closing the umbrella early.

Deliverables: current child map, superseded assumptions, #49 terminal dependency, and closure checklist.

Tests: compare closed #40, active #41/#48/#49/#196, and closed `054` evidence.

Acceptance: #10 closes only after #49 succeeds and its other remaining acceptance is routed.

### I-03: Close or supersede stale acquisition issue #108

Lane: W3 with W0 verification.

Priority: P1.

Dependencies: I-01 and a safe acquisition checkpoint.

Purpose: prevent an obsolete batch-002 recipe from being rerun against the current live acquisition architecture.

Deliverables: evidence comparison naming PR #120's obsolete live REST-route disablement, PR #151's replacement operator chain, PR #166's live REST smoke/transfer evidence, separate disposition of #108's independent review and five stylistic cleanup items, residual tasks if any, and issue disposition.

Tests: inspect current commands and live artifacts rather than relying on the issue's dated body.

Acceptance: the obsolete execution recipe is evidence-closed without accidentally discarding any independently unsatisfied review or cleanup item.

### I-04: Defer acquisition refactor issues #67 and #97 until checkpoint

Lane: W3 then W0 or a fresh cleanup worktree.

Priority: P2 until live acquisition stops.

Dependencies: I-01 and immutable acquisition checkpoint.

Purpose: preserve useful cleanup work without colliding with running authenticated paths.

Deliverables: explicit wait condition; for #67, failure run cards for `CycleAcquisitionStoreError`, a rename/compatibility strategy for `decision_filed_on_or_after` to `eligibility_anchor`, targeted regression tests, and a repository search; for #97, one shared motion-targeting helper, an explicit `docket` regex/case-number false-positive decision, planner/bridge parity tests, narrow PRs, and updated issue status.

Tests: acquisition fixtures, replay compatibility, store migrations, and full ingestion suite.

Acceptance: no path/field rename occurs under a live stage.

Acceptance: both issues close after narrow behavior-preserving fixes or documented supersession.

### I-05: Decide whether issue #37 gates Cycle 1

Lane: W1, W3, and John.

Priority: P0 decision, implementation priority based on decision.

Dependencies: current provider credential path and protected workflow design.

Purpose: decide whether workload identity federation is a Cycle 1 dispatch blocker or a post-Cycle-1 hardening milestone.

Deliverables: threat-model decision, existing credential lifetime/scope evidence, implementation estimate, and explicit gate status.

Tests: credential-path review and least-privilege validation.

Acceptance: `5qd6.41` states the decision and cannot silently ignore an unresolved security gate.

### I-06A: Finish the exact protocol/path residuals in #56

Lane: W2 or W3.

Priority: P0 and immediately ready.

Dependencies: current #56 code and acceptance evidence.

Purpose: close the specific remaining protocol/path defects in #56 without waiting on the broader artifact-ingress architecture.

Deliverables: decoded immutable-URL path validation, recursive rejection of non-string keys in `ToolRequest.arguments` and `ToolResponse.output`, and positive fixtures for 40- and 64-character commit SHAs.

Tests: encoded path bypass, nested list/map keys, invalid key types, valid 40-character SHA, valid 64-character SHA, and current protocol regression suite.

Acceptance: every checkbox in #56 is either proven by merged evidence or covered by this narrow patch.

### I-06B: Harden hostile external artifact ingress

Lane: W2 or W3.

Priority: P0 before accepting external artifacts.

Dependencies: I-06A, H-01, F-03 through F-07, and H-06.

Purpose: extend the narrow #56 fix into the complete hostile-artifact boundary required for community submissions.

Deliverables: scheme/host rules, redirect policy, immutable identity, content hash, size and file-count limits, archive/path defenses, LFS-pointer handling, and tests.

Tests: mutable URL, redirect, hash mismatch, decompression bomb, traversal archive, symlink, LFS pointer, oversized artifact, excessive file count, and undeclared content.

Acceptance: public comparison rows cannot depend on mutable or unverified content.

Acceptance: the broader ingress task does not keep #56 open after its exact residual acceptance is satisfied.

### I-07: Harden release path #42

Lane: W3.

Priority: P1; blocks public package release only if a release is required.

Dependencies: packaging decision and protected environment policy.

Purpose: make PyPI publication least-privilege and reproducible without blocking source-checkout pilots unnecessarily.

Deliverables: evidence that merged PR #51 already completed tag-only publication and full-SHA action pins, plus the remaining live environment/ref restrictions, approval/admin-bypass policy, first verified OIDC publication, provenance, release check, and rollback guidance.

Tests: build, inspect wheel/sdist, trusted-publisher dry path, unauthorized ref/environment, admin-bypass policy, first protected OIDC publication, and artifact hash verification.

Acceptance: a source-checkout pilot may proceed if no package release is required.

Acceptance: any actual release satisfies #42 before publication.

### I-08: Route future adapter issues #43 through #47

Lane: W3.

Priority: P2 after first acceptance.

Dependencies: I-01 and the named reactivation conditions below.

Purpose: reuse the proven adapter seam rather than let five adapters diverge.

Deliverables: per-issue delta analysis, priority order, prerequisites, owner, exact reactivation condition, and milestone.

Tests: manifest compatibility and no duplicate Claude/Codex scope.

Acceptance: #43 remains Responses API, #44 remains Claude Agent SDK, #45 Hermes, #46 OpenClaw, and #47 LQ.AI.

Acceptance: none is mislabeled as satisfying Claude Code or Codex CLI work.

Acceptance: #43 and #44 reactivate after C-D1 proves the adapter seam and maintainers select the next API/SDK baseline.

Acceptance: #45 and #46 reactivate after the first stratified pilot or a named demand/priority review, whichever is explicitly selected.

Acceptance: #47 remains externally blocked until Legal Quants supplies a supported API or CLI contract, auth method, test deployment, scope, and permission; branding is not treated as the technical blocker.

### I-09: Split post-Cycle-1 methods issue #6

Lane: W3 with methods review.

Priority: P2.

Dependencies: official Cycle 1 publication or an earlier explicit methods need.

Purpose: preserve Legal Quants feedback without changing the frozen first-cycle protocol midstream.

Deliverables: implemented/obsolete/residual classification, focused successor issues, and milestone assignments.

Tests: compare frozen methods and actual Cycle 1 report.

Acceptance: no post-output methods change is back-applied to Cycle 1.

### I-10: Reconcile stale live Beads

Lane: W3.

Priority: P1.

Dependencies: I-01 and live code/PR evidence.

Purpose: clean tracker state without confusing it with branch/worktree cleanup.

Deliverables: status corrections for `3uky`, `db5z`, `ue7`, `yr43`, `eb5`, and other verified stale records; relations to canonical work; and comments with evidence.

Tests: live `bd show`, merged PR check, acceptance verification, and cycle scan.

Acceptance: no Bead closes solely because its implementation branch existed.

Acceptance: `gww5`, `fup3`, and `um7q` retain their distinct active/deferred/future meanings.

### I-11: Create Codex CLI GitHub ownership

Lane: W3.

Priority: P1.

Dependencies: roadmap umbrella issue.

Purpose: create a focused Codex CLI Harvey LAB issue before adapter implementation, without conflating it with #43.

Deliverables: a focused Codex CLI Harvey LAB issue linked from the roadmap, with model/harness naming, auth profiles, runtime/LAB dependencies, tests, and acceptance evidence.

Tests: duplicate audit against #43 and existing Beads.

Acceptance: Codex CLI has a named owner, acceptance criteria, dependencies, and terminal evidence route before A-07 begins.

### I-12: Run final issue and Beads acceptance audit

Lane: W3 plus independent reviewer.

Priority: P1 at roadmap close.

Dependencies: official launch, community acceptance, and all issue-disposition tasks.

Purpose: verify the cleanup goal from live state rather than declaring it by plan completion.

Deliverables: live issue list, live nonclosed Beads list, mapped deferrals, unresolved blockers, and closure update on the roadmap issue.

Tests: `gh issue list`, `gh pr list`, `bd list`, `bd ready`, `bd dep cycles`, and artifact evidence spot checks.

Acceptance: every remaining open item is intentionally deferred or blocked with an exact reactivation condition.

### Q-01: Enforce repository static quality gates

Lane: every worktree, coordinated by W3.

Priority: P0 before merge.

Dependencies: each code task.

Purpose: keep parallel speed from degrading type, format, or documentation quality.

Deliverables: clean Ruff format/check, strict Pyright, configured documentation coverage, and actionlint for workflow changes.

Tests: `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, repo-specific doc checks, and `actionlint` where applicable.

Acceptance: no bypassed hook or unexplained warning.

### Q-02: Preserve focused unit and contract tests

Lane: every implementation owner.

Priority: P0.

Dependencies: behavior change.

Purpose: make each task independently reviewable and debuggable.

Deliverables: failing characterization or regression test first where practical, implementation, and focused green test set.

Tests: task-specific tests named in each package.

Acceptance: every bug/security boundary has a negative test that fails under the previous behavior.

### Q-03: Run full test suite at PR checkpoints

Lane: integrator for each worktree.

Priority: P0.

Dependencies: focused tests green.

Purpose: detect cross-package breakage before merge.

Deliverables: full pytest output, release-check output, and any opt-in integration result required by the PR.

Tests: `uv run pytest -q` and `uv run scripts/release_check.py` or the current repo equivalents.

Acceptance: failures are fixed or precisely attributed to an independently verified unrelated main-branch issue before merge policy decides.

### Q-04: Add deterministic fixture E2E

Lane: W2 and W0 for their respective tracks.

Priority: P0.

Dependencies: stable service contracts.

Purpose: exercise complete pipelines without network, credentials, or charges.

Deliverables: official exact-100 fixture rehearsal and community fake-binary package-to-site rehearsal.

Tests: clean temp root, interrupted run, resume, invalid artifact, and golden outputs.

Acceptance: CI proves orchestration, not merely isolated functions.

### Q-05: Add opt-in real-binary drift probes

Lane: W2.

Priority: P1.

Dependencies: A-03 and A-06.

Purpose: catch local CLI drift without making CI require subscriptions.

Deliverables: `--probe` commands, machine-readable result, no provider call by default, and docs.

Tests: current installed Claude and Codex binaries, fake incompatible versions, and absent executable.

Acceptance: probe output is safe to attach to issues and contains no auth metadata beyond category.

### Q-06: Add hostile security E2E

Lane: W2 with independent review.

Priority: P0 before real tool tasks.

Dependencies: R-09 and R-10.

Purpose: prove containment and solver/grader separation under malicious behavior.

Deliverables: hostile adapter/task fixtures, canaries, observed network audit, process/container cleanup check, private/public tree scan, and report.

Tests: all canary and abuse cases from R-09 plus hidden-grader access and next-row contamination.

Acceptance: no canary appears in any public artifact, private persisted log, surviving process, or observed non-provider network request.

### Q-07: Add contributor-package adversarial validation

Lane: W2 and W3.

Priority: P0 before accepting external PRs.

Dependencies: F-07 and I-06.

Purpose: treat community submissions as hostile data, never executable code.

Deliverables: file/row/depth/byte quotas, identifier sanitization, Markdown and CSV escaping, archive defenses, undeclared-file rejection, and immutable reference checks.

Tests: Markdown injection, CSV formula injection, JSON depth bomb, duplicate IDs, overlapping shards, selective omission, executable payload, symlink, LFS pointer, and mutable URL.

Acceptance: credential-free read-only CI validates data without executing contributor adapters.

### Q-08: Pin protected workflow actions

Lane: W1 and W3 in isolated workflow PRs.

Priority: P0 before protected official secrets/OIDC and P0 before external submission acceptance.

Dependencies: workflow inventory.

Purpose: remove mutable third-party action tags from high-trust workflows.

Deliverables: SHA pins, update comments, provenance review, and Dependabot/Renovate path if configured.

Tests: actionlint, workflow parse, pin audit, and dry-run/reusable workflow smoke where possible.

Acceptance: official protected workflows and community validation use immutable action revisions.

### Q-09: Verify actual versus requested parallelism

Lane: W2.

Priority: P1.

Dependencies: current runner behavior.

Purpose: stop metadata from claiming concurrency that the serial runner did not provide.

Deliverables: either reject `max_parallelism != 1` or implement bounded row concurrency with accurate scheduling receipts.

Tests: requested value 1, unsupported value greater than 1, deterministic ordering, cancellation, shared cap, and concurrent output isolation if implemented.

Acceptance: published provenance records actual scheduling semantics.

### Q-10: Run fresh-eyes reviews

Lane: all.

Priority: P0 before merge.

Dependencies: code and tests complete.

Purpose: challenge false-success states that authors naturally miss.

Deliverables: architecture review, security review where applicable, artifact inspection, issue/acceptance cross-check, and resolved findings.

Tests: reviewer reproduces at least one negative path and one clean path.

Acceptance: the reviewer is not the dominant author of the code under review.

### Q-11: Rebuild public artifacts from a clean checkout

Lane: W3.

Priority: P0 before publication.

Dependencies: official or community package complete.

Purpose: prove that reports are derived from committed code and declared artifacts.

Deliverables: clean-checkout environment receipt, lockfile hash, build command, output hashes, diff report, and rendered inspection.

Tests: bit-for-bit rebuild for credential-free score/report stages and link/render validation.

Acceptance: unexplained drift blocks publication.

### Q-12: Record reproducibility receipts

Lane: W1 and W2.

Priority: P0 for live results.

Dependencies: runtime and artifact contracts.

Purpose: define reproducibility as frozen inputs and verifiable derivations rather than identical provider text.

Deliverables: release SHA, lockfile hash, OS/architecture, image digest, CLI distribution/version/hash, requested/resolved model, settings, timestamps, run order, retries, usage, deliverable hashes, grader hashes, and package hashes.

Tests: receipt schema, changed-input mismatch, clean score recomputation, and clean site rebuild.

Acceptance: provider nondeterminism and unresolved aliases are disclosed.

Acceptance: rows with unresolved model identity do not silently composite with supposedly identical rows.

## 17. Testing strategy

### 17.1 Test layers

Layer 0 is the trusted-operator Tier-0 paired smoke.

It uses one pinned public task, hash-verified solver-visible bytes, physical solver/evaluator separation, native whole-process outer containment, sealed output before evaluation, frozen caps/order/claims, and allowlist-only scanned publication.

Layer 0 is not hostile-contributor validation and cannot satisfy #49.

Layer 1 is pure schema and policy validation.

It covers versioned records, required fields, hashes, compatibility keys, state transitions, and error classification.

Layer 2 is filesystem and process contract testing.

It covers materialization, path safety, output discovery, subprocess lifecycle, redaction, receipts, and resume identity.

Layer 3 is deterministic fixture end to end.

It covers the complete official downstream path with fake providers and the complete community package-to-site path with fake CLIs and evaluator.

Layer 4 is hostile boundary integration.

It covers real Docker or Podman isolation, canaries, network denial, process cleanup, solver/grader separation, and malicious package data.

Layer 5 is opt-in live capability and credential smoke.

It covers installed CLI drift, selected auth mode, bounded provider connectivity, model resolution, and private redaction.

Layer 6 is paid one-task acceptance.

It covers real solve, deliverable, common evaluation, score verification, package validation, and site rebuild.

Layer 7 is prespecified pilot execution.

It covers multiple tasks, repeats, randomized order, paired compatibility, failure denominators, uncertainty, and budget reconciliation.

Layer 8 is official protected dispatch.

It covers frozen packets, shards, receipts, accepted attempts, exact aggregate, audit, and official publication.

### 17.2 Community test matrix

| Concern | Offline unit/contract | Fake-binary E2E | Hostile container E2E | Opt-in live probe | Paid smoke |
| --- | --- | --- | --- | --- | --- |
| Task identity | Required | Required | Required | N/A | Required |
| Solver/grader split | Required | Required | Required with canary | N/A | Required |
| Deliverable discovery | Required | Required | Required | N/A | Required |
| Score normalization | Required | Required | N/A | N/A | Required |
| Trusted score verification | Required | Required | N/A | N/A | Required |
| Auth profile selection | Required | Required with fake | Required with canary | Required | Required |
| CLI capability drift | Required with fake | Required | N/A | Required | Required |
| Native whole-process containment | Policy required | Fake boundary required | Required for contributor grade | Required no-spend | Tier 0 narrow / Tier 1 full |
| MCP-mediated secondary arm | Protocol required | Fake tool required | Required only for mediated profile | Optional no-spend | Not required for clean-native arm |
| Timeout cleanup | Required | Required | Required | Optional | Required |
| Resume identity | Required | Required | Required | N/A | Required |
| Redaction | Required | Required | Required across private/public trees | Required | Required |
| Package safety | Required | Required | Malicious data required | N/A | Required |
| Aggregate compatibility | Required | Required | N/A | N/A | Required |
| Site rebuild | Required | Required | N/A | N/A | Required |

### 17.3 Official test matrix

| Concern | Unit/contract | Exact-100 fixture | Workflow smoke | Official run |
| --- | --- | --- | --- | --- |
| Source reconciliation | Required | Required | N/A | Verified artifact |
| Projection determinism | Required | Required | N/A | Verified artifact |
| Purchase idempotency | Required | Failure drill | N/A | Ledger audit |
| Parser/label secret scoping | Required | Missing-secret case | Optional auth smoke | Stage receipt |
| Unitization/adjudication | Required | Full flow | N/A | Closure audit |
| Cycle label audit | Required | Pass and fail cases | N/A | Lawyer evidence |
| Packet leakage | Required | Adversarial fixture | N/A | Pre-freeze audit |
| Shard provenance | Required | Synthetic schedule | Required | Every dispatch |
| Concurrency identity | Expression test | N/A | Required | Run queue evidence |
| Finalizer receipts | Required | Synthetic union | Required | Every shard |
| Accepted-attempt map | Required | Multiple-attempt fixture | Failure drill | If rerun occurs |
| Provider cap | Required | Concurrent simulation | Required | Ledger audit |
| Fan-in completeness | Required | Missing/extra cells | Verify-only | Required |
| Official aggregate | Required | Golden | No publication | Required |

### 17.4 Required quality commands

Use the exact commands configured by the repository at execution time.

The expected baseline is:

```bash
uv sync --all-extras --dev
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest -q
uv run scripts/release_check.py
```

Use the repository's configured workflow-lint target for workflow changes; if none exists, run `actionlint` from the repository root so both `.yml` and `.yaml` workflows are covered.

Use focused test invocations during TDD and the full suite before each PR checkpoint.

Do not add `requirements.txt`, call `pip`, or bypass hooks.

### 17.5 Coverage and mutation emphasis

Preserve any configured coverage gate.

Prioritize branch coverage on fail-closed validators and state machines.

Use property or fuzz testing for contributor-controlled identifiers, JSON size/depth, path normalization, selection determinism, and receipt mutation.

Use explicit negative controls rather than relying on line coverage for security claims.

Mutation testing and recurring binary-drift sweeps are post-launch improvements unless a concrete defect makes one critical; they never displace a ready Tier-0 or official task.

### 17.6 Real-service test policy

Real provider and evaluator calls are opt-in and budgeted.

Every paid test has a prespecified maximum spend and terminal call count.

Every live test records the exact task, model, auth profile, executable identity, and reason.

Offline CI remains the default and must not fail merely because contributor credentials are absent.

No real-service test runs on an untrusted pull request.

## 18. Launch gates

### 18.1 Gate O-A: acquisition reconciliation

- [ ] The full July source set is terminal or has an exact pending ledger.

- [ ] The 22 complaint replays are terminal.

- [ ] CourtListener REST recovery precedes Firecrawl residual fallback.

- [ ] All active REST/HTML replay artifacts are integrated.

- [ ] Candidate counts conserve across successes, exclusions, and pending states.

- [ ] At least 100 clean eligible cases exist or a shortfall stops the launch.

- [ ] Every projection-eligible case has a verified canonical qualifying decision date on or after June 30, 2026.

### 18.2 Gate O-B: cohort policy

- [ ] John records immutable `launch_case_count=100` before model output; at least 150 remains the reserve objective.

- [ ] The intended official model universe, registry hash, deployment/release evidence, and authority for the inclusive `2026-06-30` anchor are frozen.

- [ ] The deterministic projection and tie-breaking policy are frozen.

- [ ] The source-pool and selected-case hashes are frozen.

- [ ] The projection policy hard-codes the inclusive `2026-06-30` cutoff and fails closed on missing or earlier dates.

- [ ] The replacement cutoff and authority are frozen.

- [ ] Live Beads edges match the chosen policy.

### 18.3 Gate O-C: downstream corpus

- [ ] Supported disclosure review artifacts exist.

- [ ] Purchase decisions and cycle-wide cap are approved.

- [ ] Parser and labeling Infisical folders exist and are least-privilege.

- [ ] All required documents are validated and hash-bound.

- [ ] Parsing, unitization, adjudication, labeling, and human audit are complete.

- [ ] Exactly 100 packet manifests and packet hashes are stable.

- [ ] Final summary and exclusion ledgers reconcile.

### 18.4 Gate O-D: official eval readiness

- [ ] Shard schedule and dispatch-provenance schema pass.

- [ ] Workflow shard-only and concurrency behavior pass.

- [ ] Finalizer receipts and accepted-attempt fan-in pass.

- [ ] Cycle-wide spend and attempt ledger passes failure drills.

- [ ] Provider isolation and secret redaction pass.

- [ ] Exact-100 fixture downstream rehearsal passes.

- [ ] Live workflow smoke and verify-only fan-in pass.

- [ ] John completes citation and security decisions.

### 18.5 Gate O-E: official launch

- [ ] The release SHA and lockfile are pinned.

- [ ] The freeze binds packets, labels, registry, policies, schedule, budgets, and receipts.

- [ ] The pre-dispatch docket/outcome check confirms forecast-time eligibility.

- [ ] Every dispatched case still satisfies the frozen inclusive `2026-06-30` anchor, and a model-universe change has not invalidated the projection.

- [ ] Model-visible packets contain no labels, outcome material, sealed/private files, hidden grader material, or post-cutoff evidence.

- [ ] John records out-of-band go/no-go approval.

- [ ] Exactly one canonical dispatch path is used.

- [ ] Every shard finishes or follows the frozen recovery policy.

- [ ] Fan-in verifies before aggregation.

### 18.6 Gate C-T0: preliminary native paired smoke

- [ ] Issue #196 has a recorded Phase A preliminary / Phase B reproducible amendment.

- [ ] Provider automation and result-publication terms are recorded for the selected auth profile.

- [ ] The LAB revision/evaluator seam and exact Claude Code binary/hash are pinned.

- [ ] The primary Claude arm preserves native local tools and configures no task MCP server.

- [ ] Byte-identical solver-visible inputs are physically separate from evaluator-private bytes.

- [ ] Task, arms, model/settings, evaluator/judge, order, caps, timeout, retry, metrics, and claims are frozen before spend.

- [ ] The solver runs inside the narrow disposable outer boundary; output is sealed before separate evaluation.

- [ ] Public artifacts are allowlist-built and independently scanned for credentials, account/path data, private transcripts, and grader canaries.

- [ ] Score, coverage, tokens, cost basis, wall-clock, attempts, and failures are published together.

- [ ] Every surface says `Preliminary — one task pair, operator-run, not independently reproducible`; #49 remains open.

Claude Tier-0 completion does not wait for the Codex fast-follow.

### 18.6A Gate C-T0C: nonblocking Codex Tier-0 follow-on

- [ ] The pinned Codex binary preserves its clean-install native loop and enumerated local tools inside the verified narrow outer boundary.

- [ ] A Codex-specific model/resource/order/evaluator addendum was committed before any Codex or paired-native spend.

- [ ] The addendum reuses the exact pinned solver-visible task projection and evaluator seam without changing the Claude Tier-0 artifacts.

- [ ] Output seals before arm-opaque separate evaluation, and all attempts/failures remain visible.

- [ ] The reviewed package reports score, coverage, cost basis, tokens, wall-clock, attempts, failures, and exact compatibility-key result.

- [ ] Every surface says `Preliminary — one task pair, operator-run, not independently reproducible`; #49 remains open and no generalized Claude-versus-Codex claim appears.

### 18.7 Gate C-A: community measurement foundation

- [ ] Solver input and evaluator-private input are separate.

- [ ] Canonical task, deliverable, score, and run-summary schemas pass.

- [ ] Compatibility and claim taxonomy are implemented.

- [ ] Metrics propagate through package, aggregate, and site.

- [ ] Trusted score recomputation or receipt verification is implemented.

- [ ] Contributor artifacts are treated as hostile data.

### 18.8 Gate C-B: contributor-grade runtime and auth

- [ ] The native whole-process boundary enforces the clean-native claim.

- [ ] The issue #41 runtime separately enforces any accepted MCP-mediated profile.

- [ ] Process groups and containers are fully cleaned up.

- [ ] Host environment projection excludes ambient configuration.

- [ ] Auth profiles are explicit and fail closed.

- [ ] Claude and Codex capability probes pass.

- [ ] Hostile canaries fail to escape or leak.

- [ ] `max_parallelism` reflects actual scheduling.

### 18.9 Gate C-C: LAB bridge and adapters

- [ ] The LAB upstream revision, license, and CLI are pinned.

- [ ] Real run/evaluate behavior replaces obsolete flags.

- [ ] External deliverables can be evaluated without rerunning solvers.

- [ ] Native LAB, clean-native Claude Code, and clean-native Codex fake E2Es pass.

- [ ] Claude Code and Codex real binary no-spend probes pass.

- [ ] Adapter identities remain distinct from SDK/API adapters.

### 18.10 Gate C-D1: first contributor-grade community acceptance

- [ ] The one-task smoke design is committed before spend.

- [ ] The Claude Code real run succeeds and passes trusted regrade.

- [ ] The package validates from a clean checkout.

- [ ] The static site rebuild is bit-for-bit reproducible.

- [ ] Privacy, credential, canary, and undeclared-file scans pass.

- [ ] Issue #49 links the accepted submission.

The first #49 acceptance does not wait for Codex or a matched native arm because #49 requires one real adapter.

Tier-0 evidence cannot satisfy this gate.

### 18.11 Gate C-D2: dual-adapter and comparison readiness

- [ ] The Codex real run succeeds and passes trusted regrade.

- [ ] Both Claude Code and Codex contributor paths have reproducibility receipts and documentation.

- [ ] The dual-adapter aggregate and site rebuild from a clean checkout.

### 18.12 Gate C-D3: matched native-LAB comparison

- [ ] A matched native arm uses the exact same committed solver-visible content, served model identity, provider route, model settings, evaluator, judge, temporal block, outer boundary class, run order, and repeat policy.

- [ ] Harness-intrinsic system prompt, context management, loop, tool API, and tool implementation differences are frozen and disclosed as the treatment; they are not incorrectly required to be identical.

- [ ] A versioned layout adapter may change filesystem layout only when its mapping proves no semantic material was added or removed.

- [ ] The prespecified pilot identifies which rows are matched harness comparisons and which are harness-plus-model system bundles.

- [ ] A `matched_harness_key` exists before reporting a matched paired observation; generalized effect language additionally waits for the prespecified multi-task/repeat pilot and supported uncertainty.

- [ ] Unresolved served-model identity or any mismatched nuisance variable forces system-bundle language.

## 19. GitHub issue terminal map

| Issue | Current role | Planned route | Launch relationship |
| --- | --- | --- | --- |
| #6 | Legal Quants methods feedback | Split after Cycle 1 into implemented, obsolete, and focused successors | Does not block first run unless a frozen-methods requirement is truly missing |
| #10 | Community umbrella | Update child map; close only after #49 | Blocks declaration of community launch complete |
| #37 | Workload identity for official providers | P0 gate decision; implement now or explicitly defer with threat-model evidence | May block official dispatch, never acquisition |
| #41 | Host-owned MCP-mediated tool runtime | Complete under `2dnr` as a secondary profile and hostile-contributor mechanism | Does not block the native Tier-0 arm; blocks any accepted mediated profile |
| #42 | PyPI trusted publishing | Complete before package release | Does not block source-checkout pilot |
| #43 | OpenAI Responses adapter | Reactivate after C8/C-D1 proves the adapter seam | Does not satisfy Codex CLI |
| #44 | Claude Agent SDK adapter | Reactivate after C8/C-D1 proves the adapter seam | Does not satisfy Claude Code |
| #45 | Hermes bridge | Reactivate after the first pilot or named demand/priority review | Does not block first community run |
| #46 | OpenClaw bridge | Reactivate after the first pilot or named demand/priority review | Does not block first community run |
| #47 | LQ.AI bridge | Remains externally blocked until Legal Quants supplies a supported API/CLI contract, auth method, test deployment, scope, and permission | Does not block technical pilot |
| #48 | Harvey LAB bridge redesign | Implement real pinned run/evaluate bridge | Blocks real LAB acceptance |
| #49 | First real community submission | Reuse first successful real adapter run | Canonical community acceptance gate |
| #56 | Protocol and immutable URL hardening | Finish before external artifacts | Blocks community artifact acceptance |
| #67 | Acquisition error audit/name cleanup | Defer until acquisition checkpoint, then narrow PR | Must not collide with live acquisition |
| #97 | Motion-target helper drift | Defer until acquisition checkpoint, then narrow PR | Benchmark-integrity cleanup, not immediate live blocker |
| #108 | Stale batch-002 execution recipe | Evidence-close or narrow residual | Do not rerun obsolete recipe |
| #196 | Claude Code headless LAB | Amend into Phase A preliminary clean-native paired smoke plus Phase B contributor-grade native adapter; keep MCP-mediated as a distinct secondary arm | Tier 0 is the first result; Phase B is the preferred #49 path |

The new roadmap issue is the cross-track portfolio record; a separate focused Codex CLI Harvey LAB issue is created at roadmap publication so Codex does not remain an indefinite unowned roadmap bullet.

## 20. Beads conversion design

### 20.1 Tracker rules and live baseline

Use the live bd database as the operational source of truth.

Do not initialize another tracker, use absent br, or make decisions from stale bv output before a fresh export.

At planning time the live store has 661 records: 578 closed and 83 nonclosed, with no dependency cycles.

The passive .beads/issues.jsonl export is stale and is refreshed only after live graph validation.

Use canonical full IDs when assigning parents.

Use parent-child hierarchy for grouping, blocks edges for execution order, related links for historical association, and explicit merge-and-refresh checkpoint tasks for actual PR barriers.

The installed `bd` build accepts `merge-request` in dry-run but rejects that type during actual issue validation, so checkpoint nodes use ordinary task type with the full merge/refresh contract in title and acceptance.

A closed predecessor such as 054 remains closed and related only.

The active 2dnr record remains the sole owner for GitHub issue 41 runtime receipts, resume binding, and negative controls.

Every new task has a self-contained purpose, deliverables, tests, and acceptance criteria.

Every graph mutation includes a cycle check, targeted dependency inspection, and ready-queue inspection.

Two labels identify the launch-critical queues: `critical-path-official` and `critical-path-tier0`.

`contributor-intake` marks the full reproducible path that follows Tier 0.

`off-critical-path` and `post-launch` mark parked work.

Every executor queries its critical label first and excludes both `off-critical-path` and `contributor-intake` from the ordinary queue while same-lane critical work is ready.

An agent may claim off-critical-path work while critical work is ready in the same lane only when the coordinator records the blocking reason on the critical Bead.

### 20.2 Portfolio hierarchy

Create these top-level records:

| Handle | Type and parent | Priority | Purpose |
| --- | --- | --- | --- |
| PORT | top-level epic | P0 | Govern both launch tracks and the issue-convergence program; link the roadmap issue |
| PLAN-MR | merge/refresh checkpoint task under PORT | P0 | Land this plan, both roadmap issues, the initial graph, review evidence, and worktree refresh |
| PLAN-VALIDATE | task under PORT | P0 | Validate the initial live graph and refresh the passive export |
| PORT-CRITICAL | task under PORT | P0 | Enforce critical-path labels, WIP rule, dated escalation, and post-launch tracker pruning |
| COMM | epic under PORT | P0 | Successor community-comparison program, related to closed 054 |
| ISSUES | epic under PORT | P1 | GitHub issue and stale-tracker convergence |
| DIST | epic under PORT | P0 | Publication, audience, LegalQuants engagement, README, and methods preprint |

Relate PORT to existing official epic 5qd6, closed community predecessor 054, active runtime owner 2dnr, and background branch-cleanup record gww5.

Do not create another official epic or a generic quality epic.

New official governance tasks live directly under 5qd6 or 5qd6.73.

Static checks, focused tests, the full suite, and fresh-eyes review are acceptance requirements of every merge checkpoint rather than free-floating recurring Beads.

Live materialization on 2026-07-16:

| Scope | Live ID or namespace |
| --- | --- |
| PORT | `dm0g` |
| PLAN-MR / PLAN-VALIDATE | `dm0g.2` / `dm0g.3` |
| COMM / ISSUES | `dm0g.4` / `dm0g.5` |
| PORT-CRITICAL / DIST | `dm0g.6` / `dm0g.7` |
| Efficiency / native boundary / native E2E | `dm0g.4.1.16` / `dm0g.4.2.15` / `dm0g.4.2.16` |
| Optional mediated profiles | `dm0g.4.4.15` |
| Claude Tier-0 critical path | `dm0g.4.5.12` through `dm0g.4.5.16` |
| Codex Tier-0 fast-follow | `dm0g.4.5.17` and `dm0g.4.5.18` |
| Distribution children | `dm0g.7.1` through `dm0g.7.8` |
| Post-launch tracker pruning | `dm0g.5.15` |
| Official pre-dispatch registry/anchor recheck | `5qd6.96` |
| Community foundation | `dm0g.4.1.*` |
| Runtime | `dm0g.4.2.*` |
| LAB bridge | `dm0g.4.3.*` |
| Adapters | `dm0g.4.4.*` |
| First acceptance | `dm0g.4.5.*` |
| Pilot/contributor work | `dm0g.4.6.*` |
| New official governance/checkpoints | `5qd6.86` through `5qd6.95` |
| New acquisition reconciliation tasks | `5qd6.73.39` through `5qd6.73.41` |

Use live `bd show` or `bd list --parent` for the exact title-to-ID mapping; the live database remains authoritative after this snapshot.

The initial conversion created 105 records: 92 in the `dm0g` portfolio namespace and 13 under existing official parents.

The strategic amendment adds only bounded Tier-0, native-boundary, efficiency, scheduling, and distribution records; it labels or re-prioritizes the existing long tail instead of cloning it.

Live materialization of the amendment added 23 records: one scheduler, one distribution epic and eight distribution children, five Claude Tier-0 tasks, two Codex Tier-0 tasks, efficiency/native-boundary/native-E2E/optional-mediated tasks, one tracker-pruning task, and one official pre-dispatch registry/anchor task.

The post-amendment validation snapshot contains 792 live records: 584 closed and 208 nonclosed.

Those counts are descriptive only and will drift as concurrent agents work; live `bd` remains authoritative.

Validation task `dm0g.3` closed after proving zero cycles, unchanged dependency state for the three active acquisition executors, singular `2dnr` runtime ownership, launch-readiness edges for `5qd6.39.11`, `.39.6`, and `.39.10`, and a refreshed passive export of 766 records.

### 20.3 Official additions under existing 5qd6

| Handle | Type and parent | Blocking dependencies | Terminal evidence |
| --- | --- | --- | --- |
| O-DECIDE | decision under 5qd6 | PLAN-MR | Immutable launch_case_count=100 and reserve policy recorded before output |
| O-SOURCE-SCOPE | task under 5qd6.73 | PLAN-MR | All 15 currently nonclosed source children and any later arrivals classified from live evidence |
| O-COMPLAINT-ORDER | task under 5qd6.73 | O-SOURCE-SCOPE | Safe checkpoint, REST-first ordering, and regenerated exact residual input |
| O-POLICY-MR | merge/refresh checkpoint task under 5qd6 | O-DECIDE, O-SOURCE-SCOPE | Parameterized projection/reconciliation policy code merged and owning worktree refreshed; 5qd6.36 still gates the immutable projection |
| O-RECONCILE | task under 5qd6.73 | O-POLICY-MR plus every required lane named by O-SOURCE-SCOPE | Complete reconciled universe with at least launch_case_count eligible cases |
| O-PREELIGIBILITY | task under 5qd6 | O-RECONCILE, 5qd6.39.7 | Supported disclosure decisions and noncharging cost feasibility bound to the projection pool |
| O-PROJECT | task under 5qd6 | O-DECIDE, 5qd6.36, O-RECONCILE, O-PREELIGIBILITY, 5qd6.73.1 | Immutable exact cohort and deterministic ranked reserve |
| O-GRAPH-MIGRATION | task under 5qd6 | O-PROJECT, O-POLICY-MR | Make-before-break launch edge migration completed and validated |
| O-LEGACY-MAP | task under 5qd6 | PLAN-MR | ue7.32 and ur6 obligations mapped to canonical smoke/run evidence |
| O-W1-CP1 | merge/refresh checkpoint task under 5qd6 | 5qd6.25 | PR URL/SHA, green checks, fresh review, refreshed worktree |
| O-W1-CP2 | merge/refresh checkpoint task under 5qd6 | O-W1-CP1, 5qd6.26 | Second protocol checkpoint merged and refreshed |
| O-W1-CP3 | merge/refresh checkpoint task under 5qd6 | O-W1-CP2, 5qd6.27 | Fan-in checkpoint merged and refreshed |
| O-W1-SMOKE-GATE | merge/refresh integration checkpoint task under 5qd6 | O-W1-CP3, 5qd6.28, 5qd6.29, 5qd6.32, 5qd6.33, 5qd6.34 | All official engineering inputs integrated from current main and smoke-ready |
| O-ANCHOR-REVALIDATE | task under 5qd6 | 5qd6.36; directly blocks 5qd6.41 | Within-24-hour served-model/registry/anchor evidence and explicit drift decision |

The source-scope inventory begins with the 15 live nonclosed children observed on 2026-07-16: .1, .5, .6, .7, .8, .9, .10, .23, .24, .25, .28, .32, .33, .34, and .37.

That list is a starting snapshot, not a hard-coded universe.

The strategic audit also observed in-progress grandchildren `.73.34.1` and `.73.37.1`; because a parent-child link is not a blocking edge, O-SOURCE-SCOPE must decide whether each is terminal evidence required by O-RECONCILE and add its exact edge only if required.

Do not add new blockers directly to .73.34, .73.37, or yr43.67.

Let active acquisition continue and make O-RECONCILE consume terminal evidence.

Add the yr43.67 to .73.28 ordering only through O-COMPLAINT-ORDER after confirming no final fallback pass is currently running.

Wire O-W1-CP1 to block .26, O-W1-CP2 to block .27, and O-W1-CP3 to block .29.

Wire O-W1-SMOKE-GATE and the GitHub issue 37 decision task to block .35.

The likely legacy mapping is that .35 and .39.6 satisfy rehearsal evidence for ue7.32, while .41 satisfies canonical-run evidence for ur6; verify acceptance before changing either status.

### 20.4 Community measurement foundation

Create P0 epic COMM-F under COMM.

| Handle | Depends on | Purpose |
| --- | --- | --- |
| F-ARCH | PLAN-MR | Amend or supersede ADR 0001 with the measured modular boundary and split triggers |
| F-IMPORT | F-ARCH | Freeze current import exceptions and reject new reverse dependencies |
| F-CHAR | PLAN-MR | Characterize closed-054 artifacts, readers, migration behavior, and native fixtures |
| F-RUN-CONTRACT | F-CHAR, R-CLAUDE-FEAS, R-CODEX-FEAS | Define neutral RunSpec, ExecutionReceipt, identity keys, and resume binding |
| F-MATERIALIZER | F-CHAR, L-UPSTREAM, I-56A | Build deterministic safe task materialization |
| F-SEPARATION | F-MATERIALIZER | Physically separate solver-visible and evaluator-private bytes |
| F-DELIVERABLE | F-SEPARATION, L-UPSTREAM | Add canonical validated deliverables and layout mapping |
| F-EVALUATION | F-DELIVERABLE, L-UPSTREAM | Add EvaluationSpec and EvaluationReceipt |
| F-SCORE | F-EVALUATION, F-CHAR | Add deterministic MetricDefinition and ScoreArtifact |
| F-EFFICIENCY | F-RUN-CONTRACT, F-EVALUATION, F-SCORE | Define authoritative usage/cost/time/coverage joins and public peer-column semantics |
| F-MR1 | F-IMPORT, F-RUN-CONTRACT, F-MATERIALIZER, F-SEPARATION, F-DELIVERABLE, F-EVALUATION, F-SCORE, F-EFFICIENCY | Land contract foundation and refresh W2 |
| F-SUMMARY | F-MR1, R-MR | Extend run summaries with execution/deliverable/evaluation/score references |
| F-PUBLISH | F-SUMMARY, F-EFFICIENCY | Propagate score, coverage, usage, cost basis, tokens, time, attempts, and failures through package, aggregate, and site |
| F-COMPARE | F-MR1, F-PUBLISH, F-EFFICIENCY | Add repeat, coverage, efficiency, failure estimand, compatibility, and claim policies |
| I-56B | F-MR1 | Harden redirects, archives, LFS pointers, decompression, parsers, and hostile submission ingress |
| I-WORKFLOW | F-MR1 | Cover adapter examples, both adapter namespaces, full-SHA pins, and actual workflow path filters |
| F-MR2 | F-PUBLISH, F-COMPARE, I-WORKFLOW, I-56B | Land measurement/publication behavior and refresh |

I-56A is the narrow residual needed before materialization: decoded immutable-URL path validation, recursive non-string-key rejection, and positive 40/64-character SHA tests.

I-56B is the larger hostile-artifact boundary and must not recreate the earlier dependency cycle.

### 20.5 Runtime and LAB bridge

Create sibling P0 epics COMM-RUNTIME and COMM-LAB under COMM.

Runtime records:

| Handle | Depends on | Purpose |
| --- | --- | --- |
| PROVIDER-TERMS | PLAN-MR | Verify supported automation/auth modes and result-publication rights before provider-specific implementation, spend, or publication |
| R-CLAUDE-FEAS | PROVIDER-TERMS | No-spend proof that native Claude tools and loop work inside a disposable outer boundary without ambient config/web/private access |
| R-CODEX-FEAS | PROVIDER-TERMS | Equivalent native-sandbox/outer-boundary proof for Codex CLI |
| R-PROCESS | PLAN-MR | Process-group cancellation and descendant cleanup |
| R-AUTH | F-RUN-CONTRACT | Generic auth schema, provenance category, and no-fallback rules |
| R-ENV | R-AUTH | Minimal host environment and credential projection |
| R-SERVICE | F-MR1, R-PROCESS, R-AUTH, R-ENV | Shared local-CLI execution service |
| R-CAPABILITY | R-SERVICE | Executable capability identity and structured event framing |
| R-REDACT | R-SERVICE | Central transcript and secret redaction |
| R-MR | R-CAPABILITY, R-REDACT | Land the shared local runtime and refresh |
| R-PARALLELISM | R-SERVICE | Enforce requested-versus-actual scheduling truth and fail closed on divergence |
| R-HOSTILE-E2E | R-MR, 2dnr, F-SEPARATION, I-56B | Full hostile runtime plus solver/grader canary E2E beyond 2dnr unit canaries |
| R-NATIVE-BOUNDARY | R-CLAUDE-FEAS, R-CODEX-FEAS, R-ENV, F-SEPARATION, Tier-0 observations | Contributor-grade whole-process native containment with provider-only egress and separate evaluation |
| R-NATIVE-E2E | R-NATIVE-BOUNDARY, R-REDACT, F-SEPARATION, I-56B | Hostile native whole-process and solver/evaluator canary E2E |
| AUTH-API | PROVIDER-TERMS, R-AUTH, R-ENV | Explicit API-key published profile |
| AUTH-SUBSCRIPTION | PROVIDER-TERMS, R-NATIVE-E2E, relevant adapter checkpoint | Contributor-owned local subscription profile; P1 and nonblocking for Tier 0 |

R-MR also depends on R-PARALLELISM.

Do not create new receipt, resume-binding, or issue-41 unit/negative-canary owners for the mediated profile.

The clean-native outer boundary is a different whole-process responsibility and therefore has its own bounded records rather than overloading `2dnr`.

Expand 2dnr acceptance or decompose it only with its current owner if more granularity is needed.

LAB records:

| Handle | Depends on | Purpose |
| --- | --- | --- |
| L-UPSTREAM | PLAN-MR | Pin the issue-196 LAB revision, characterize real run/evaluate behavior, and prove the evaluator seam before contracts freeze |
| L-PROJECTION | F-MR1, L-UPSTREAM | Implement LAB suite projection only |
| L-OUTPUT | F-MR1, L-UPSTREAM | Implement safe output discovery only |
| L-EVALUATOR | F-EVALUATION, F-SCORE, F-SEPARATION, L-UPSTREAM, L-OUTPUT | Invoke the evaluator in an isolated hostile-input boundary |
| L-VERIFY | L-EVALUATOR, F-PUBLISH | Verify authorized evaluator receipts and deterministically recompute normalization |
| L-MR | L-PROJECTION, L-OUTPUT, L-EVALUATOR, L-VERIFY | Land the pinned LAB bridge and refresh |
| L-NATIVE | L-EVALUATOR | Implement native LAB comparison arm; P1 and not a blocker of first acceptance |
| X-SPEC | F-MR2, F-EFFICIENCY, L-UPSTREAM, L-PROJECTION, PROVIDER-TERMS, T0-PUBLISH | Freeze the Tier-1 issue-196 task, inputs, criteria, caps, hashes, efficiency fields, and claims after learning from Tier 0 |

A fresh stochastic judge invocation creates a new measurement receipt and repeat index; it is never verification of a previous score.

### 20.6 Claude and Codex adapters

Create P0 epic COMM-ADAPTERS under COMM.

| Handle | Depends on | Purpose |
| --- | --- | --- |
| A-MANIFEST | F-RUN-CONTRACT | Generic local-CLI adapter manifest |
| A-CLAUDE-FAKE | PLAN-MR | Fake executable and deterministic error/stream fixtures |
| A-CLAUDE-PROBE | A-CLAUDE-FAKE, R-CLAUDE-FEAS | Current-binary capability and version characterization |
| A-CLAUDE-OFFLINE | A-MANIFEST, A-CLAUDE-PROBE, F-MR1, R-SERVICE | Offline command builder, parser, fixture deliverable, and conformance |
| A-CODEX-FAKE | PLAN-MR | Fake executable and deterministic error/JSONL fixtures |
| A-CODEX-PROBE | A-CODEX-FAKE, R-CODEX-FEAS | Current-binary capability and version characterization |
| A-CODEX-OFFLINE | A-MANIFEST, A-CODEX-PROBE, F-MR1, R-SERVICE, I-CODEX-ISSUE | Offline Codex core and conformance |
| AUTH-CLAUDE | A-CLAUDE-OFFLINE, AUTH-API | Bind approved auth profiles to Claude |
| AUTH-CODEX | A-CODEX-OFFLINE, AUTH-API | Bind approved auth profiles to Codex |
| A-CLAUDE-LIVE | A-CLAUDE-OFFLINE, AUTH-CLAUDE, R-MR, R-NATIVE-BOUNDARY, R-NATIVE-E2E, L-MR | Real `claude-code-clean-native` adapter |
| A-CODEX-LIVE | A-CODEX-OFFLINE, AUTH-CODEX, R-MR, R-NATIVE-BOUNDARY, R-NATIVE-E2E, L-MR | Real `codex-cli-clean-native` adapter |
| A-MEDIATED | 2dnr, R-HOSTILE-E2E, applicable offline/auth tasks | P2 optional MCP-mediated decomposition profiles with distinct identities |
| A-REGISTRY | A-MANIFEST, F-MR1 | Generic registry/entry-point integration without concrete adapter branching |
| A-CLAUDE-MR | A-CLAUDE-LIVE, A-REGISTRY | Claude PR merged, fresh review complete, W2 refreshed |
| A-CODEX-MR | A-CODEX-LIVE, A-REGISTRY | Codex PR merged, fresh review complete, temporary Codex worktree refreshed |

The fake/probe tasks are intentionally ready early.

Offline cores proceed after neutral contracts exist; clean-native live activation waits for the whole-process native boundary and LAB bridge.

The issue #41 mediated boundary is required only for A-MEDIATED.

W2 carries both adapters while exact reservations remain disjoint; only measured collision pressure justifies parking W3 and recreating that counted slot for an independent Codex PR.

### 20.7 First acceptance and later pilot

Create P0 epic COMM-ACCEPT and P1 epic COMM-PILOT under COMM.

Tier-0 critical path records under COMM-ACCEPT:

| Handle | Depends on | Purpose |
| --- | --- | --- |
| T0-GOV | PROVIDER-TERMS | Amend #196 and freeze intended clean-native primary/mediated secondary identities, publication rights, threat model, claims, and date while feasibility/pin probes run in parallel |
| T0-SPLIT | L-UPSTREAM, R-CLAUDE-FEAS | Build the narrow one-task solver-visible projection, evaluator-private inventory/canaries, safe output locator, and separate evaluator invocation |
| T0-SPEC | T0-GOV, T0-SPLIT, installed Claude capability evidence | Commit the exact paired task/model/settings/tools/order/caps/retry/evaluator/metrics/claims before spend |
| T0-RUN | T0-SPEC | Run clean-native Claude plus native thin LAB where feasible, preserve all attempts, seal outputs, and evaluate separately |
| T0-PUBLISH | T0-RUN | Independently review/redact, archive the preliminary package, update #196, and unblock the public writeup |
| T0C-SPEC | T0-SPLIT, R-CODEX-FEAS | Freeze the nonblocking Codex/native-LAB addendum, capability inventory, matched resource policy, evaluation order, budget, and claims before spend |
| T0C-PUBLISH | T0C-SPEC | Execute, independently review, and publish the Codex Tier-0 follow-on without blocking T0-PUBLISH |

All seven records carry `critical-path-tier0` and `tier-0`; the Codex pair also carries `codex-tier0` and has no dependency path into T0-PUBLISH.

T0-PUBLISH blocks the later Tier-1 X-SPEC so the reusable factory incorporates observed upstream/CLI behavior.

No Tier-0 record blocks or satisfies X-PACKAGE/X-MR or issue #49.

| Handle | Depends on | Purpose |
| --- | --- | --- |
| X-CLAUDE-HANDSHAKE | A-CLAUDE-MR, R-MR | Private no-tool credential/redaction handshake |
| X-CODEX-HANDSHAKE | A-CODEX-MR, R-MR | Private no-tool credential/redaction handshake |
| X-SECURITY-E2E | F-MR2, L-MR, R-NATIVE-E2E | Shared clean-native package-to-site, clean rebuild, and hostile foundation acceptance |
| X-CLAUDE-E2E | X-SECURITY-E2E, A-CLAUDE-MR | Claude fake-binary package-to-site acceptance |
| X-CODEX-E2E | X-SECURITY-E2E, A-CODEX-MR | Codex fake-binary package-to-site acceptance |
| X-CLAUDE | X-SPEC, X-CLAUDE-HANDSHAKE, X-CLAUDE-E2E | Tier-1 contributor-grade clean-native Claude smoke with stop-after-one cap |
| X-CODEX | X-SPEC, X-CODEX-HANDSHAKE, X-CODEX-E2E | Tier-1 contributor-grade clean-native Codex smoke with stop-after-one cap |
| X-PACKAGE | X-CLAUDE, L-VERIFY | Package, verify, validate, and rebuild the first real #49 submission |
| X-MR | X-PACKAGE | First accepted community row PR merged and W2 refreshed |
| X-DUAL | X-MR, X-CODEX | Dual-adapter enablement gate |
| X-NATIVE | X-DUAL, L-NATIVE | Decide and, only with exact compatibility, execute matched native smoke |
| PILOT-FREEZE | X-DUAL, F-COMPARE, X-NATIVE decision | Freeze stratified pilot, estimands, order, caps, stopping, and omission rules |
| PILOT-RUN | PILOT-FREEZE | Execute and publish the prespecified pilot |
| DOCS-CONTRIBUTOR | X-DUAL, AUTH-SUBSCRIPTION | Reproducible contributor workflow |
| POLICY-SUBMISSION | X-MR, L-VERIFY, F-PUBLISH | Acceptance, quarantine, correction, revocation, and withdrawal policy |
| LEGALFORECAST-PUBLIC | 5qd6.41, X-DUAL | Later disclosure-safe public LegalForecast task projection; P2 |

Claude is the deterministic dependency for #49.

If Claude becomes externally blocked after all supported in-scope paths are exhausted, create a bounded decision record that may rewire X-PACKAGE to X-CODEX; do not encode an ordinary OR edge.

Matched native comparison does not block #49.

### 20.8 Distribution and engagement

Create P0 epic DIST under PORT.

| Handle | Depends on | Purpose |
| --- | --- | --- |
| D-CALENDAR | PLAN-MR | Freeze audiences, evidence/claim tiers, forbidden language, owners, URLs, approvals, and dates |
| D-OFFICIAL-SHELL | D-CALENDAR | Build the fixture-backed Cycle 1 human report/leaderboard now |
| D-OFFICIAL-PUBLISH | D-OFFICIAL-SHELL, 5qd6.41 | Populate, independently audit, publish, and update README within 24 hours |
| D-HARNESS-WRITEUP | D-CALENDAR, T0-PUBLISH | Publish the preliminary Claude paired writeup with score/coverage/cost/tokens/time/attempts/failures and permanent label; append T0C-PUBLISH when ready without delaying Claude |
| D-LQ-DRAFT | D-CALENDAR | Draft the immediate Jamie response, intended native-tools design pending feasibility, pilot co-design invitation, and result follow-up; no external send |
| D-LQ-JOHN | D-LQ-DRAFT; result follow-up also waits for D-HARNESS-WRITEUP | John approves/sends or declines and closes the bounded feedback window |
| D-PREPRINT | draft: D-CALENDAR; final: D-OFFICIAL-PUBLISH | Draft 6–10 page methods paper now; final SSRN package after audited official results; include a labeled harness appendix only if ready without delay; John controls submission |
| D-README | D-CALENDAR | Make README the landing page and require result-link refresh within 24 hours |

PILOT-FREEZE depends on D-LQ-JOHN's feedback-window closure state, not on LegalQuants sending a response.

Distribution work never blocks the underlying Tier-0 run or official dispatch; it blocks only its own publication products and the pre-score pilot-input window.

### 20.9 Issue convergence

Create P1 epic ISSUES under PORT, with the following children:

| Handle | Depends on | Purpose |
| --- | --- | --- |
| I-MAP | PLAN-MR | One live issue-to-Bead-to-code-to-terminal-evidence map; owns both P-04 and I-01 |
| I-CODEX-ISSUE | roadmap publication | Create and link the focused Codex CLI Harvey LAB issue before adapter implementation |
| I-37 | PLAN-MR | Decide GitHub issue 37 OIDC gate status; blocks 5qd6.35 until implemented or explicitly deferred |
| I-10 | I-MAP, X-MR | Reconcile community umbrella issue 10 |
| I-108 | I-MAP, O-RECONCILE | Evidence-close or narrow issue 108 using PRs 120, 151, and 166 plus residual review |
| I-67 | I-MAP, immutable acquisition checkpoint | CycleAcquisitionStoreError run cards and eligibility_anchor migration; P2 |
| I-97 | I-MAP, immutable acquisition checkpoint | Shared motion-target helper and regex/parity decision; P2 |
| I-42 | I-MAP | Preserve PR 51 evidence and complete only residual live OIDC/environment/ref checks |
| I-FUTURE | I-MAP | Record exact reactivation conditions for issues 43 through 47 |
| I-6 | I-MAP, official Cycle 1 evidence | Split methods feedback into satisfied, obsolete, and focused residuals |
| I-STALE | I-MAP | Reconcile stale/overlapping live Beads; relate to gww5 without waiting for branch deletion |
| I-WORKFLOW | PLAN-MR | Audit protected workflow full-SHA pins and actual adapter path filters |
| I-FINAL | 5qd6.41, X-DUAL, I-10, I-108, I-STALE | Final live GitHub and Beads acceptance audit |

Use external refs such as gh-37 and gh-41 in titles/descriptions so GitHub issue numbers are never confused with Beads 5qd6.37 and 5qd6.41.

### 20.10 Merge and refresh checkpoint contract

Every merge-and-refresh checkpoint node requires all of the following evidence:

- PR URL and merge commit SHA.

- Repository-required static checks, type checks, and full tests green.

- Focused negative and characterization tests green.

- Fresh-eyes review by an agent who did not author the dominant change.

- No unresolved correctness or security finding.

- Workflow validation with the repository target or actionlint covering both .yml and .yaml when workflows change.

- Owning worktree stopped and refreshed or recreated from merged origin/main.

- Targeted post-refresh characterization rerun when the checkpoint changes code, generated artifacts, commands, schemas, protocols, security boundaries, or downstream-consumed interfaces.

- Docs-only and test-only checkpoints record `not applicable` instead of running redundant post-refresh characterization when they change no executable interface.

Downstream implementation depends on the checkpoint node, not merely on code that exists on an unmerged branch.

No shared worktree carries two concurrent PR branches.

### 20.11 Work-package-to-Bead disposition ledger

Every detailed package in section 16 has exactly one operational disposition below.

Multiple packages map to one Bead only where one is the contract/policy facet of the same terminal deliverable.

| Work package | Disposition / owner | Role | PR checkpoint |
| --- | --- | --- | --- |
| P-01 | new PLAN-MR | planning deliverable | PLAN-MR |
| P-02 | new O-DECIDE plus O-GRAPH-MIGRATION | governance and graph cutover | O-POLICY-MR |
| P-03 | new O-LEGACY-MAP | evidence mapping | PLAN-MR |
| P-04 | new I-MAP, same owner as I-01 | issue map | PLAN-MR |
| P-05 | PLAN-MR runbook consumed by every merge node | recurring acceptance | every merge node |
| P-06 | new PLAN-VALIDATE; repeated inside later mutations | bounded validation | PLAN-MR |
| O-00 | new O-SOURCE-SCOPE | source-universe gate | O-POLICY-MR |
| O-01 | existing 5qd6.73.34 | acquisition execution | existing owner |
| O-02 | existing 5qd6.73.37 | streaming screen | existing owner |
| O-03 | existing yr43.67 | complaint replay | existing owner |
| O-04 | new O-COMPLAINT-ORDER | safe graph/order change | O-POLICY-MR |
| O-05 | new O-RECONCILE | launch-count gate | O-POLICY-MR |
| O-05A | existing 5qd6.36, with accepted registry/freeze evidence from 5qd6.24 | methods authority | existing owner and O-POLICY-MR |
| O-06 | new O-PROJECT | immutable cohort | O-POLICY-MR |
| O-07 | existing 5qd6.75 | nonblocking reserve | existing owner |
| O-08 | existing 5qd6.39.7 | disclosure producer | existing owner |
| O-08A | new O-PREELIGIBILITY | projection input | O-POLICY-MR |
| O-09 | existing 5qd6.37 | purchase decision | existing owner |
| O-10 | existing 5qd6.76 | John credential-folder blocker | existing owner |
| O-11 | existing 5qd6.39.11 | operator/runbook conformance | production checkpoint |
| O-12 | existing 5qd6.39.6 | provider-free E2E | production checkpoint |
| O-13 | existing 5qd6.39 production family | assemble/refresh/disclosure | 5qd6.39 |
| O-14 | existing 5qd6.39 production family | purchase/download | 5qd6.39 |
| O-15 | existing 5qd6.39 production family | parse/normalize | 5qd6.39 |
| O-16 | existing 5qd6.39 production family | unitize/adjudicate | 5qd6.39 |
| O-17 | existing 5qd6.39 production family | label/audit | 5qd6.39 |
| O-18 | existing 5qd6.39 production family | packets/final ledgers | 5qd6.39 |
| O-19 | existing 5qd6.25 plus O-W1-CP1 | shard/provenance | O-W1-CP1 |
| O-20 | existing 5qd6.26 plus O-W1-CP2 | shard workflow/finalize | O-W1-CP2 |
| O-21 | existing 5qd6.27 plus O-W1-CP3 | receipts/fan-in | O-W1-CP3 |
| O-22 | existing 5qd6.29 plus O-W1-SMOKE-GATE | accepted attempts | O-W1-SMOKE-GATE |
| O-23 | existing 5qd6.28 | spend/attempt ledger | O-W1-SMOKE-GATE |
| O-24 | existing 5qd6.32, .33, and .34 | isolation/caps/runbook | O-W1-SMOKE-GATE |
| O-25 | existing 5qd6.35 | live smoke | existing gate |
| O-25A | new 5qd6.96 | within-24-hour registry/anchor revalidation | John-operated dispatch gate |
| O-26 | existing 5qd6.41 | official dispatch | John-operated gate |
| O-27 | existing 5qd6.41; 5qd6.40 is post-launch follow-up | audit/aggregate/publish | canonical run |
| F-01 | new F-ARCH | ADR amendment | F-MR1 |
| F-01A | new F-IMPORT | early import budget | F-MR1 |
| F-02 | new F-CHAR | current behavior characterization | F-MR1 |
| F-02A | new F-RUN-CONTRACT | run/receipt contracts | F-MR1 |
| F-03 | new F-MATERIALIZER | generic task materializer | F-MR1 |
| F-04 | new F-DELIVERABLE | deliverable contract | F-MR1 |
| F-04A | new F-EVALUATION | evaluation spec/receipt | F-MR1 |
| F-05 | new F-SCORE | metric/score artifact | F-MR1 |
| F-05A | new F-EFFICIENCY | authoritative cost/token/time/coverage joins | F-MR1/F-MR2 |
| F-06 | new F-SUMMARY | summary references | F-MR2 |
| F-07 | new F-PUBLISH | package/aggregate/site | F-MR2 |
| F-08 | new F-COMPARE | comparisons/estimands | F-MR2 |
| F-09 | F-IMPORT enforcement plus F-ARCH policy | import boundary | F-MR1 |
| F-10 | I-WORKFLOW, shared safely with Q-08 | CI examples/path coverage | isolated workflow PR and F-MR2 |
| R-00A | R-CLAUDE-FEAS, amended to native outer-containment | no-spend native feasibility | C0/Tier-0 evidence |
| R-00B | R-CODEX-FEAS, amended to native sandbox/outer-containment | no-spend native feasibility | nonblocking C0b/Tier-0 Codex evidence |
| R-00C | new R-NATIVE-BOUNDARY | contributor-grade whole-process native boundary | C3N |
| R-01 | existing 2dnr | secondary issue-41 MCP-mediated runtime | existing owner / C3M |
| R-02 | existing 2dnr | receipt/resume binding | existing owner / C3M |
| R-03 | new R-PROCESS | process cleanup | R-MR |
| R-04 | new R-AUTH | generic auth schema | R-MR |
| R-05 | new R-ENV | minimal environment | R-MR |
| R-06 | new R-SERVICE | shared execution service | R-MR |
| R-07 | new R-CAPABILITY | probes/framing | R-MR |
| R-08 | new R-REDACT | central redaction | R-MR |
| R-09 | existing 2dnr; full mediated E2E is R-HOSTILE-E2E under Q-06 | MCP-mediated runtime canaries | existing owner / C3M mediated acceptance |
| R-09A | new R-NATIVE-E2E | hostile whole-process native boundary E2E | C3N/Tier-1 gate |
| R-10 | new F-SEPARATION | generic trust-domain policy | F-MR1 |
| H-01 | L-UPSTREAM | pinned LAB source | L-MR |
| H-02 | L-UPSTREAM | command characterization | L-MR |
| H-00 | L-UPSTREAM | evaluator seam gate | C0 evidence |
| H-03 | new L-PROJECTION | LAB suite plugin | L-MR |
| H-04 | new L-OUTPUT | output discovery | L-MR |
| H-05 | new L-EVALUATOR | isolated evaluator | L-MR |
| H-06 | new L-VERIFY | trusted receipt/normalization | L-MR |
| H-07 | new L-NATIVE | native comparison arm | later claim gate |
| H-08 | new X-SPEC | exact smoke fixture | smoke gate |
| A-01 | new A-MANIFEST | generic adapter schema | R-MR |
| A-02 | new A-CLAUDE-FAKE | fake executable | A-CLAUDE-MR |
| A-03 | new A-CLAUDE-PROBE | real binary probe | A-CLAUDE-MR |
| A-04A | new A-CLAUDE-OFFLINE | offline core | A-CLAUDE-MR |
| A-04 | A-CLAUDE-LIVE amended to clean-native | live native-contained adapter | A-CLAUDE-MR |
| A-05 | new A-CODEX-FAKE | fake executable | A-CODEX-MR |
| A-06 | new A-CODEX-PROBE | real binary probe | A-CODEX-MR |
| A-07A | new A-CODEX-OFFLINE | offline core | A-CODEX-MR |
| A-07 | A-CODEX-LIVE amended to clean-native | live native-contained adapter | A-CODEX-MR |
| A-08 | new A-REGISTRY | generic registry/entry points before concrete adapters | both adapter checkpoints |
| A-09 | new AUTH-SUBSCRIPTION | contributor auth profile | contributor docs |
| A-10 | new AUTH-API | published auth profile | adapter checkpoints |
| A-11 | new AUTH-CLAUDE | Claude binding | A-CLAUDE-MR |
| A-12 | new AUTH-CODEX | Codex binding | A-CODEX-MR |
| A-13 | new A-MEDIATED | optional post-launch mediated decomposition profiles | post-launch PR |
| E-01 | PROVIDER-TERMS expanded to result-publication rights | policy decision | C0 evidence |
| E-00A | new T0-GOV | issue amendment/native-treatment governance | C0/Tier-0 |
| E-00B | new T0-SPLIT plus T0-SPEC | narrow paired path and frozen prespecification | C-T0a |
| E-00C | new T0-RUN plus T0-PUBLISH | paid paired smoke and reviewed preliminary package | C-T0b |
| E-00D | new T0C-SPEC | nonblocking Codex Tier-0 addendum and dry run | C-T0c |
| E-00E | new T0C-PUBLISH | reviewed paid Codex Tier-0 follow-on package | C-T0c |
| E-02 | new X-CLAUDE-HANDSHAKE and X-CODEX-HANDSHAKE | per-provider handshakes | live smoke |
| E-03 | new X-SPEC | prespecification | live smoke |
| E-03A | create only on a proven external Claude blocker | conditional governance | not created initially |
| E-04 | new X-CLAUDE | first paid smoke | X-MR |
| E-05 | new X-CODEX | parallel paid smoke | X-DUAL |
| E-06 | new X-NATIVE | matched-pair observation only if compatible | pilot decision |
| E-07 | new X-PACKAGE plus X-MR | #49 acceptance | X-MR |
| E-08 | new PILOT-FREEZE | prespecification | pilot |
| E-09 | new PILOT-RUN | execution/results | pilot result PR |
| E-10 | new DOCS-CONTRIBUTOR | contributor instructions | docs PR |
| E-11 | new POLICY-SUBMISSION | submission governance | policy PR |
| E-12 | new LEGALFORECAST-PUBLIC | later public suite | post-launch PR |
| D-00 | new D-CALENDAR | audience/claim/publication calendar | D0 |
| D-01 | new D-OFFICIAL-SHELL | fixture-backed official report shell | D0 |
| D-02 | new D-OFFICIAL-PUBLISH | audited official report publication | D2 |
| D-03 | new D-HARNESS-WRITEUP | preliminary paired writeup | D1 |
| D-04A | new D-LQ-DRAFT | draft LegalQuants engagement; no send | D0 |
| D-04B | new D-LQ-JOHN | John send/decline and bounded feedback window | human checkpoint |
| D-05 | new D-PREPRINT | methods preprint source/package | D3 |
| D-06 | new D-README | repository landing page | D0 and result refreshes |
| I-01 | new I-MAP, same Bead as P-04 | terminal map | PLAN-MR |
| I-02 | new I-10 | GitHub issue 10 | X-MR |
| I-03 | new I-108 | GitHub issue 108 | acquisition checkpoint |
| I-04 | split into new I-67 and I-97 | unrelated deferred fixes | separate PRs |
| I-05 | new I-37 | GitHub issue 37 decision | official smoke |
| I-06A | new I-56A | exact issue-56 residual | F-MR1 |
| I-06B | new I-56B | expanded hostile ingress | F-MR2 |
| I-07 | new I-42 | residual release hardening | release PR |
| I-08 | new I-FUTURE | exact issue 43-47 routes | planning update |
| I-09 | new I-6 | post-Cycle-1 methods split | post-run |
| I-10 | new I-STALE | live Beads reconciliation | issue audit |
| I-11 | new I-CODEX-ISSUE | focused GitHub ownership | roadmap publication |
| I-12 | new I-FINAL | live terminal audit | final checkpoint |
| Q-01 | acceptance on every merge node | static quality | every PR |
| Q-02 | acceptance on each implementation task | focused tests | every PR |
| Q-03 | acceptance on every merge node | full suite | every PR |
| Q-04 | existing 5qd6.39.6 plus new X-SECURITY-E2E, X-CLAUDE-E2E, and X-CODEX-E2E | split official/community deterministic E2E | corresponding gates |
| Q-05 | initial A-CLAUDE-PROBE/A-CODEX-PROBE remain launch work; recurring sweeps are `post-launch` | capability evidence then maintenance | adapter PRs/post-launch |
| Q-06 | R-NATIVE-E2E for clean-native plus R-HOSTILE-E2E/L-EVALUATOR for mediated/evaluator paths | profile-specific hostile runtime/evaluator | contributor/LAB gates |
| Q-07 | I-56B and X-SECURITY-E2E | adversarial package validation | F-MR2/X |
| Q-08 | I-WORKFLOW, `contributor-intake`; do not displace Tier 0 | protected workflow audit | workflow PR before external intake/protected use |
| Q-09 | R-PARALLELISM, `contributor-intake`; PLAN-VALIDATE retains checkpoint truth | requested/actual scheduling and graph | pilot/runtime checkpoint |
| Q-10 | acceptance on every merge node | fresh-eyes review | every PR |
| Q-11 | X-SECURITY-E2E and X-PACKAGE | clean-checkout rebuild | X-MR |
| Q-12 | ExecutionReceipt/EvaluationReceipt tasks and live runs | reproducibility receipts | corresponding gates |

### 20.12 Exact official edge migration

Do not perform this cutover until PLAN-MR is merged, O-DECIDE records launch_case_count=100, O-SOURCE-SCOPE is complete, and the replacement nodes exist.

First add replacement dependencies, using bd syntax where the blocked issue is the first argument:

```text
O-PROJECT blocks 5qd6.37
O-PROJECT blocks 5qd6.39
5qd6.39.11 blocks 5qd6.39.6
5qd6.39.6 blocks 5qd6.39
5qd6.39.10 blocks 5qd6.39
O-W1-SMOKE-GATE blocks 5qd6.35
I-37 blocks 5qd6.35
O-ANCHOR-REVALIDATE blocks 5qd6.41
```

After each addition, require an empty cycle output and inspect both the purchase and production blocker sets.

Only after replacement edges exist:

```text
remove 5qd6.38 as a blocker of 5qd6.39
remove 5qd6.75 as a blocker of 5qd6.39
remove 5qd6.73 as a blocker of 5qd6.39
remove 5qd6.73 as a blocker of 5qd6.37
```

The acquisition umbrella and reserve work remain related and active; they simply cease to gate the exact-100 production pass.

### 20.13 Validation sequence

After each creation or mutation batch run live checks equivalent to:

```bash
bd dep cycles --json
bd ready --exclude-type epic --json
bd dep list 5qd6.39 --direction=down --json
bd dep list 5qd6.37 --direction=down --json
bd dep tree 5qd6.41 --direction=down --show-all-paths
bd list --parent LegalForecastBench-5qd6.73 --all --flat --json
```

Final assertions:

- Cycle output is an empty array.

- The exact projection is a blocker of both purchase and production after cutover.

- Continuing loop .38, reserve .75, and umbrella .73 are no longer transitive official-launch blockers through .39.

- .39.6, .39.10, and .39.11 are represented in production readiness.

- No active acquisition task was unexpectedly blocked or status-mutated.

- Initial ready work exists in official eval, current-artifact characterization, LAB characterization, process/auth work, Claude/Codex probes, provider policy, and issue mapping.

- Closed 054 remains closed and related only.

- 2dnr remains the sole issue-41 runtime owner.

- Tier-0 reaches T0-PUBLISH without a transitive dependency on 2dnr, F-MR1/F-MR2, hostile contributor ingress, or X-PACKAGE.

- Codex T0C-PUBLISH depends on the shared narrow split and Codex feasibility but has no dependency path into or through Claude T0-PUBLISH.

- A-CLAUDE-LIVE and A-CODEX-LIVE use R-NATIVE-BOUNDARY/R-NATIVE-E2E rather than silently requiring the MCP-mediated tool profile.

- `bd ready --label critical-path-official` and `bd ready --label critical-path-tier0` expose the next actionable non-epic work when their prerequisites close; ordinary work excludes both `off-critical-path` and `contributor-intake` while either same-lane queue is ready.

- Every parked task carries `off-critical-path` or `post-launch`, and ordinary executor queries exclude both `off-critical-path` and `contributor-intake` while same-lane critical work is ready.

- DIST has no blocking edge into the underlying official dispatch or Tier-0 execution; only the pilot input window and publication products consume its relevant evidence.

After live validation, refresh the passive export through bd export and record its count.

The export is a passive snapshot, not a substitute for subsequent live checks.
## 21. Execution waves

Dates are target and escalation controls, never permission to waive evidence, security, budget, freeze, or publication gates.

If a target misses, update the live Bead with the blocker, revised forecast, and claim/relevance consequence while continuing any safe critical-path work.

### Wave 0: amended plan, graph, and claims calendar — target 2026-07-17

Land P0 with this strategic review and amendment.

Create/validate the new Tier-0, native-boundary, efficiency, critical-scheduler, and distribution Beads.

Label the two critical paths, park the long tail, assign four primary agents per ready worktree, and publish the Agent Mail ownership maps.

Record the exact-100 recommendation and John decision task.

### Wave 1: four parallel starts — 2026-07-17 through 2026-07-18

W0 continues live acquisition and complaint recovery.

W1 starts shard-protocol and spend/isolation engineering.

W2 pins LAB/evaluator behavior, verifies provider/publication terms, amends #196, proves native Claude containment, and freezes Tier-0 governance.

W3 freezes the audience/claims calendar, starts the official report shell/README/preprint, and prepares the Jamie draft for John's send decision.

Target by 2026-07-18: #196 amendment, native-tools decision, provider/publication-terms record, claims calendar, and first Jamie send/decline decision.

No paid community task runs before the Tier-0 specification is committed.

### Wave 2: Tier-0 paired result — target 2026-07-21, hard escalation 2026-07-23

W2 stages the one pinned solver-visible task, proves the solver/private split, freezes task/model/settings/order/caps/evaluator/claims, and completes a provider-free dry run.

Run the clean-native Claude Code arm and native thin LAB arm with exact model parity where available.

Seal each output before separate evaluation, retain every attempt/failure, and independently scan/review the public package.

W3 publishes the short preliminary writeup and refreshes README within 24 hours.

If exact parity is unavailable, publish system-bundle plumbing rows rather than a harness delta.

In parallel, Agent C2 completes the Codex feasibility probe and freezes its own addendum without taking Agents C0/C1/C3 off the Claude result.

Target the reviewed Codex Tier-0 follow-on by 2026-07-23, with hard escalation on 2026-07-25; it reuses the task/evaluator seam, runs its own paired native arm where parity is feasible, and never delays the Claude publication.

### Wave 3: model cut and parallel foundations — target 2026-07-20 through 2026-07-31

Freeze the Cycle 1 model universe and registry cut by 2026-07-20; later models normally move to Cycle 2.

Land official shard/provenance foundation and continue receipts, fan-in, accounting, and workflow-smoke preparation.

Land community task/run/deliverable/evaluation/score/efficiency contracts, native whole-process boundary, pinned LAB bridge, and shared CLI runtime.

Use the Claude and available Codex Tier-0 observations to freeze the Tier-1 one-task specification without waiting past the Codex escalation date.

Target the full Claude native-adapter/reproducibility checkpoint by 2026-07-31.

### Wave 4: contributor-grade E2E and first trusted row — target 2026-08-07

Run official exact-100 provider-free downstream rehearsal.

Run community fake Claude/Codex package-to-site E2E, hostile native-boundary canaries, evaluator leakage tests, adversarial package tests, and clean-checkout rebuilds.

Finish the Tier-1 Claude smoke and trusted/rebuildable #49 row by 2026-08-07 if all gates pass.

Codex proceeds in parallel after the shared interfaces freeze but cannot delay Claude-first acceptance.

The issue #41 mediated profile continues independently and never blocks clean-native acceptance.

### Wave 5: official exact-100 freeze and dispatch — target 2026-08-13

Target source reconciliation/projection by 2026-07-24, exact-100 downstream packet readiness by 2026-08-07, and the official one-provider workflow smoke by 2026-08-11.

When every immutable gate passes, John freezes and dispatches official Cycle 1 immediately, with 2026-08-13 as the target rather than a wait-until date.

Recheck the frozen registry/served aliases and eligibility anchor within 24 hours before dispatch.

Target audited official publication by 2026-08-17 and refresh README within 24 hours.

### Wave 6: pilot and engagement — target 2026-08-12 through 2026-08-21

Close the LegalQuants pilot-input window by 2026-08-12 using feedback received, no response, or John-declined-send evidence.

Freeze the stratified pilot before any stratified-pilot score is observed, then execute only the prespecified arms/order/repeats/caps.

Target pilot publication by 2026-08-21 with score, coverage, cost, tokens, time, attempts, failures, and uncertainty where supported.

### Wave 7: methods publication and backlog convergence

Complete a preprint draft within seven days of the official report and an SSRN submission package within fourteen days; John separately approves submission.

Continue the at-least-150 official reserve extension without changing the frozen 100.

Complete deferred acquisition cleanup, mediated decomposition only if useful, release/future-adapter work, and the final issue/Beads audit.

Run a tracker-pruning pass after the two launches so stale planning mass does not obscure the ready queue.

### Wave 8: relevance reapproval and architecture reassessment — 2026-08-27

If Cycle 1 has not dispatched by 2026-08-27, require an explicit John schedule/relevance decision: continue the still-valid frozen universe, reanchor/reproject before any output, or defer the cycle.

Do not silently add a newer model or change the cohort.

Measure dependency, install, release, and ownership pressure after both launches.

Decide whether an internal CLI extraction is sufficient.

Create a `uv` workspace migration plan only if a package-split trigger is actually met.

## 22. Risk register and premortem

### RISK-01: the graph still blocks exact 100 on at least 150

Likelihood: high without P-02.

Impact: high wall-clock delay.

Signal: `5qd6.39` remains blocked only by `5qd6.75`/`5qd6.38` after 100 clean cases exist.

Mitigation: approve policy, migrate edges, and keep reserve extension independent.

Contingency: if specification requires 150 for official status, rename the 100-case run a pilot before output and update claims/budget.

### RISK-02: provisional enrichment prefix becomes a frozen cohort

Likelihood: medium.

Impact: selection bias and irreproducible source universe.

Signal: projection input lacks a completed source reconciliation hash.

Mitigation: O-05 gate and completed snapshot verification.

Contingency: invalidate the projection and rebuild before any model exposure.

### RISK-03: live acquisition is disrupted by cleanup or refresh

Likelihood: medium in a multi-agent repo.

Impact: lost checkpoint, duplicate calls, or inconsistent artifacts.

Signal: branch/code changes while an active stage writes the store.

Mitigation: sole writer, explicit file ownership, no refresh mid-stage, checkpoint first.

Contingency: stop calls, preserve store copy and logs, verify config identity, resume only through canonical recovery.

### RISK-04: a local CLI demo is mistaken for a benchmark result

Likelihood: high.

Impact: misleading public claims.

Signal: a row has provider output but no sealed deliverable/evaluator evidence, or a Tier-0 row lacks its permanent preliminary/operator-run label.

Mitigation: Gate C-T0 enforces the narrow credibility invariants and label before the preliminary row; the full measurement contracts and contributor launch gates still precede #49 acceptance.

Contingency: label the artifact private plumbing evidence and exclude it from comparison tables until the missing Tier-0 or Tier-1 evidence exists.

### RISK-05: `sandbox.plan.json` is mistaken for containment

Likelihood: high under schedule pressure.

Impact: host credential or filesystem exposure.

Signal: a row claims native containment without the whole-process boundary, or claims MCP mediation without R-01/R-09.

Mitigation: fail closed by profile: clean-native uses the outer whole-process boundary; MCP-mediated uses #41. Tier 0 uses its explicitly narrower trusted-input boundary and label.

Contingency: treat the run as a security incident if canaries or credentials were exposed; rotate as needed and do not publish.

### RISK-06: solver sees hidden grader material

Likelihood: high with the current all-artifacts LAB projection.

Impact: invalid score and benchmark contamination.

Signal: solver workspace includes rubric keys, references, judge prompts, or evaluator-only files.

Mitigation: R-10 physical trust-domain split and hidden-material canaries.

Contingency: invalidate all affected rows and rerun from a newly hashed task projection.

### RISK-07: contributor forges an internally consistent score

Likelihood: medium once submissions open.

Impact: corrupted comparison site.

Signal: CI validates hashes but cannot derive or trust-anchor the score.

Mitigation: H-06 trusted regrade or trusted evaluator receipt.

Contingency: publish execution receipt only, not comparative score, until verification exists.

### RISK-08: subscription auth exposes durable token state

Likelihood: medium to high without a proven profile.

Impact: account compromise and invalid security claims.

Signal: adapter requests full HOME, `.claude`, `.codex`, `auth.json`, keyring export, or token copy.

Mitigation: auth-profile gate, minimal projection, no token copy, canary scan, fail closed.

Contingency: keep subscription mode private plumbing-only and use explicit API key for publishable rows.

### RISK-09: provider auto-update changes the harness mid-run

Likelihood: medium.

Impact: incompatible rows or irreproducible behavior.

Signal: executable hash or version changes between probe and completion.

Mitigation: disable self-update for the run, pin distribution where supported, hash before and after.

Contingency: invalidate the row and rerun on one pinned version.

### RISK-10: timeout leaves child processes alive

Likelihood: medium under current subprocess semantics.

Impact: further spend, contamination, or secret exposure.

Signal: process/container remains after runner reports timeout.

Mitigation: process-group lifecycle and cleanup tests.

Contingency: kill the process tree/container, quarantine workspace, reconcile spend, and do not resume from its receipt.

### RISK-11: Claude/Codex comparison is misdescribed as harness effect

Likelihood: high.

Impact: invalid scientific inference.

Signal: rows differ in model identity, task inputs, judge, or evaluator but text attributes difference to harness.

Mitigation: compatibility keys and claim taxonomy.

Contingency: relabel as system-bundle comparison and remove causal language.

### RISK-12: one-task smoke is overinterpreted

Likelihood: high.

Impact: noisy or anecdotal conclusion.

Signal: rankings or general claims appear before E-08.

Mitigation: hard-coded smoke-only presentation and prespecified pilot.

Contingency: retract comparison language while retaining plumbing evidence.

### RISK-13: failures disappear from averages

Likelihood: medium.

Impact: biased scores and denominator drift.

Signal: reported task count differs by arm without explicit coverage table.

Mitigation: canonical failure states, coverage denominator, paired policy.

Contingency: rebuild aggregates with failure-inclusive policy and version the correction.

### RISK-14: official and community artifacts cross namespace

Likelihood: low to medium.

Impact: official-result contamination or private-data release.

Signal: community package references official private roots or official aggregate imports community orchestration.

Mitigation: artifact namespace, import tests, public projection boundary.

Contingency: block publication, rotate private immutable URLs if exposed, and rebuild through correct namespace.

### RISK-15: stale JSONL or `bv` drives execution

Likelihood: high until refreshed.

Impact: duplicate closed work or wrong ready queue.

Signal: robot plan lists `gr1`, `n8g`, or other live-closed tasks.

Mitigation: live `bd` validation and fresh passive export.

Contingency: discard robot recommendations and rebuild from live state.

### RISK-16: too many worktrees increase conflict instead of speed

Likelihood: medium.

Impact: integration delay and lost context.

Signal: multiple branches edit `cli.py`, `spec.py`, `runner.py`, or workflows concurrently.

Mitigation: four-lane ceiling including acquisition, four-primary role maps, Agent Mail reservations, and explicit integrator/single-writer ownership.

Contingency: pause dependent edits, land foundation, refresh, and reassign agents to disjoint files.

### RISK-17: workflow actions remain mutable

Likelihood: medium.

Impact: supply-chain risk in protected or credentialed workflows.

Signal: action refs use mutable major tags.

Mitigation: Q-08 before live high-trust runs.

Contingency: block dispatch/submission acceptance until pins and review land.

### RISK-18: package release becomes an unnecessary blocker

Likelihood: medium.

Impact: delayed pilot.

Signal: #42 blocks a source-checkout run with no PyPI requirement.

Mitigation: separate source-checkout acceptance from package publication.

Contingency: execute from pinned repository SHA and finish release hardening later.

### RISK-19: official run duplicates or reruns ambiguously

Likelihood: medium.

Impact: mixed attempts, spend, and invalid aggregate.

Signal: multiple receipts per shard without accepted-attempt map or duplicate full dispatch path.

Mitigation: one canonical `5qd6.41`, immutable receipts, explicit accepted attempts.

Contingency: stop fan-in, reconcile provider spend, commit selection map, and verify object versions.

### RISK-20: issue cleanup closes work on comments rather than evidence

Likelihood: medium.

Impact: hidden residual defects and false completion.

Signal: closure lacks tests, artifact, merged PR, or acceptance mapping.

Mitigation: I-01/I-12 evidence matrix and independent review.

Contingency: reopen or create a focused successor with exact residual acceptance.

### RISK-21: another team publishes the obvious Claude-Code-versus-LAB result first

Likelihood: high because headless Claude Code is locally available and the experiment is easy to describe.

Impact: major loss of timeliness, LegalQuants attention, and differentiated public traction.

Signal: the Tier-0 target slips past 2026-07-23 while noncritical contributor infrastructure remains in progress.

Mitigation: the seven-record `critical-path-tier0` with a five-record Claude path and two-record nonblocking Codex fast-follow, no dependency on #41/full contracts, a frozen one-task cap, and the ready-queue WIP rule.

Contingency: publish the verified preliminary plumbing result and methods/specification promptly even if exact model parity fails, using system-bundle language and no harness delta.

### RISK-22: anchor decay or model-registry staleness erodes official relevance

Likelihood: medium and increasing with delay.

Impact: served-model drift can invalidate the frozen design; unrelated frontier releases can make the result less timely even when it remains valid.

Signal: model-universe cut misses 2026-07-20, a frozen served alias/version changes, a major frontier model releases, official dispatch misses 2026-08-13, or more than six weeks elapse from this plan.

Mitigation: frozen July 20 registry cut, weekly Monday audit, within-24-hour pre-dispatch recheck, recorded anchor/registry-to-dispatch intervals, and no silent model additions.

Contingency: John explicitly chooses to continue the still-valid frozen universe, replace/reanchor and reproject before any output, or defer; on 2026-08-27 a recorded relevance/schedule decision is mandatory if not dispatched.

### RISK-23: process and tracker mass consume the launch schedule

Likelihood: high with hundreds of live records and a rich ready queue.

Impact: satisfying long-tail work starves the two result-producing paths.

Signal: an agent claims `off-critical-path` while same-lane critical work is ready; checkpoint evidence exceeds the risk of the change; or ready work cannot be distinguished from parked work.

Mitigation: critical labels, P0/P1 separation, `--exclude-label off-critical-path,contributor-intake` while same-lane critical work is ready, light docs/test checkpoint rules, one active PR per worktree, and daily integrator queue posts.

Contingency: coordinator stops new long-tail claims, reassigns primaries to the critical queue, collapses redundant checkpoint work, and runs the post-launch tracker-pruning pass.

### RISK-24: containment removes the harness feature the experiment intends to measure

Likelihood: high under the earlier MCP-first design.

Impact: the published row answers a different and less interesting question than Jamie asked.

Signal: the primary arm disables native local tools, uses Claude `--bare`, or routes task operations through the issue #41 MCP shim.

Mitigation: `clean_native` is the primary identity, the corrected matched key permits harness-intrinsic tools/loop/prompt differences as treatment, and native-tool success is a preflight assertion.

Contingency: relabel the run `mcp_mediated`, exclude it from the primary comparison, and rerun the native arm under a verified outer boundary.

## 23. Decision log

### DEC-01: first official cohort size

Cycle 1 policy: freeze an exact 100 from the clean available pool as soon as the target reconciliation gate passes; continue acquisition toward at least 150 as reserve.

Owner: John.

Deadline: before graph rewiring and before packet exposure.

Reason: it meets the stated first-run objective and removes avoidable wall-clock dependency while preserving reserve quality.

### DEC-02: monorepo now or later

Decision: later, only if measured triggers are met.

Owner: architecture lane, approved by John if a split is proposed.

Reason: current internal boundaries are sufficient for launch and a migration would collide with active work.

### DEC-03: community published auth profile

Decision: preserve explicit API key as the portable baseline profile, but let the Tier-0 operator use a provider-supported local CLI subscription profile only if the terms/publication review permits it and the row labels the cost/auth basis accurately.

Owner: community/security lane.

Reason: current product guidance treats subscription and API execution as different provenance/cost classes; publication rights and automation support must be verified rather than inferred.

### DEC-04: first community harness

Decision: clean-native Claude Code first through the narrow Tier-0 path; Codex characterization starts in parallel, a separately frozen operator-run Codex Tier-0 result fast-follows without blocking Claude, and the reusable contributor adapter proceeds once shared native interfaces freeze.

Owner: community lane.

Reason: #196 already has a detailed acceptance contract and Claude Code was the direct community request, while shared foundations make Codex cheap to add concurrently.

### DEC-05: causal comparison language

Decision: require the exact compatibility key, including exact model and resource/stopping policy, before reporting a matched paired observation; generalized `harness effect`, `performs better`, or superiority language additionally requires the prespecified multi-task/repeat pilot and supported uncertainty.

Owner: methods/review lane.

Reason: Claude Code versus Codex changes both harness and model family under ordinary local subscriptions.

### DEC-06: score trust

Decision: trusted regrade from canonical deliverable is the default.

Owner: community lane.

Fallback: a policy-defined trusted evaluator receipt only when licensing or grader architecture prevents CI regrade.

Reason: self-consistent contributor hashes do not establish score correctness.

### DEC-07: issue #37 dispatch status

Decision: pending explicit review.

Owner: John and official security lane.

Deadline: before official smoke uses the final credential design.

Reason: acquisition can continue independently, but dispatch must not silently waive a known credential-hardening issue.

### DEC-08: native tools versus MCP mediation

Decision: contain around the harness for the primary arm; preserve native tools, prompt/loop, context management, and native sandbox as the treatment.

Owner: community/methods lane.

Decision detail: issue #41 MCP mediation remains a separately named secondary arm and security mechanism, never the primary Claude Code or Codex identity.

Reason: substituting a foreign tool loop would answer a different question from whether the clean-install native agent loop and enumerated local tools change LAB performance; literal `out of the box` wording is reserved for a profile that satisfies section 8's stock-capability rule.

### DEC-09: economics and time in public comparisons

Decision: score, coverage, cost basis, tokens, wall-clock, attempts, and failures are peer headline fields; authoritative accounting stays in execution/evaluation receipts rather than being copied into ScoreArtifact.

Owner: measurement and audience lanes.

Reason: the practical efficiency tradeoff is central to law-firm and research readers, while one authoritative receipt layer prevents accounting drift.

### DEC-10: publication and schedule discipline

Decision: run a small distribution lane now and use the exact dates in section 21 as escalation targets, never gate waivers.

Owner: coordinator and W3.

Reason: a credible unpublished result creates little traction, and delay can erode relevance even when the frozen design remains logically valid.

## 24. Definitions of done

### 24.1 Official Cycle 1 done

Official Cycle 1 is done only when the exact launch cohort, packets, labels, policies, model registry, shard schedule, and budget are frozen before model output; every declared shard has an accepted immutable receipt; fan-in and exact aggregate pass; audits pass; and the descriptive report is published with a complete run card.

Having 100 case IDs is not done.

Having 100 parsed packets is not done.

Dispatching models is not done.

A green workflow with missing receipt or provenance evidence is not done.

### 24.2 First community acceptance done

The first community acceptance is done only when a real non-fixture adapter produces a validated deliverable, a trusted common evaluator produces or verifies the canonical score, the package passes hostile-data validation, the aggregate and site rebuild from a clean checkout, privacy scans pass, and the accepted submission is linked from #49.

A CLI returning text is not done.

A `sandbox.plan.json` is not done.

A contributor-authored score with matching self-hashes is not done.

A one-task smoke is not evidence of general harness superiority.

### 24.2A Claude Tier-0 preliminary result done

Tier 0 is done only when issue #196's amendment and the frozen paired specification predate spend; solver-visible bytes are identical across arms; evaluator-private material is physically absent from the solver boundary; clean-native Claude preserves native tools; output is sealed before separate evaluation; every attempt/failure is retained; score, coverage, cost basis, tokens, time, and configuration are reported; and independent artifact/claim scans pass.

Every Tier-0 public surface carries the exact label `Preliminary — one task pair, operator-run, not independently reproducible`; attempt/repeat counts are reported separately, and the result is not contributor-safe.

Tier 0 does not close #49 or prove general harness superiority.

### 24.2B Codex Tier-0 fast-follow done

The Codex fast-follow is done only when its own addendum predates spend; the pinned clean-install native Codex capability inventory and boundary probes pass; solver-visible bytes and evaluator separation reuse the frozen seam; all attempts and failures remain visible; output seals before arm-opaque evaluation; score, coverage, cost basis, tokens, wall-clock, and exact compatibility result are independently reviewed; and the Claude result was not delayed.

It carries the same permanent preliminary label, supports at most the observed paired difference for its pinned task/run, and does not close #49 or establish a Claude-versus-Codex ranking.

### 24.3 Claude and Codex enablement done

Claude Code enablement is done when the fake and real adapter paths, capability probes, auth profiles, runtime containment, deliverable, trusted score, resume, redaction, and contributor documentation pass.

Codex enablement has the same definition and remains distinct from the Responses API adapter.

Local subscription enablement is done only when the CLI can authenticate without copying durable auth state into the workspace or container and public provenance labels the category accurately.

### 24.4 Issue convergence done

Issue convergence is done when live GitHub and live Beads state show that every remaining item has a verified terminal route and all launch-critical acceptance is complete.

Closing issues mechanically is not done.

Leaving intentionally deferred issues open with exact milestone and reactivation conditions is acceptable.

### 24.5 Plan completion done

This plan is complete when it has survived five review rounds, the accepted revisions are integrated, the GitHub roadmap issue exists, the Beads graph is created with dependencies and critical-path labels, the live graph is cycle-free, initial parallel ready work exists, and the planning PR is opened.

### 24.6 Planning review record

Round 1, failure premortem and security review: added fail-closed cohort gates, hostile-input boundaries, explicit auth categories, spend separation, credential-store prohibitions, and causal-claim limits.

Round 2, architecture review: added the real LAB evaluator feasibility gate, the then-proposed Claude/Codex tool-mediation probes, the task/run/execution/deliverable/evaluation/score/analysis artifact graph, distinct identity keys, model-universe eligibility authority, and corrected dependency direction; Round 5 deliberately superseded tool mediation as the primary treatment.

Round 3, live GitHub issue review: covered all 17 open issues at the planning snapshot, split issue 56's narrow residual from broader ingress hardening, preserved issue 196's pinned/API baseline, created separate Codex ownership, made Claude the deterministic issue 49 path, and added exact reactivation/closure evidence.

Round 4, live Beads conversion review: replaced the unsafe six-lane assumption with a 15-child source-universe reconciliation, retained singular owners 5qd6 and 2dnr, made exact-100 cutover make-before-break, converted PR checkpoints into graph nodes, removed the generic quality epic, and produced the one-to-one disposition ledger.

Round 5, strategic speed/audience review: added the clean-native Claude Tier-0 path and nonblocking Codex fast-follow, corrected the matched-harness treatment and one-task claim definitions, separated native whole-process containment from issue #41 MCP mediation, labeled both result-producing paths and parked the long tail, increased per-worktree primary-agent capacity under Agent Mail, date-boxed the launches, elevated efficiency metrics, and added the distribution/LegalQuants/preprint lane.

All five reviews were read against the revised plan; accepted changes are represented throughout sections 1, 2, 7, 8, 10 through 23, and 26.

## 25. Source and evidence references

Repository-local evidence:

- `README.md`

- `pyproject.toml`

- `docs/adr/0001-community-multiharness-scope.md`

- `docs/multiharness-adapter-spec.md`

- `docs/plans/2026-07-12-cycle1-eval-readiness.md`

- `docs/plans/2026-07-12-cycle1-cohort-runbook.md`

- `docs/plans/2026-07-16-dual-track-roadmap-review.md`

- `legalforecast/multiharness/command_adapter.py`

- `legalforecast/multiharness/community.py`

- `legalforecast/multiharness/harvey_lab_adapter.py`

- `legalforecast/multiharness/runner.py`

- `legalforecast/multiharness/sandbox.py`

- `legalforecast/publication/community_aggregate.py`

- live GitHub issues #6, #10, #37, #41-#49, #56, #67, #97, #108, and #196

- live Beads records named throughout this plan

Official product references reviewed during planning:

- OpenAI Codex manual authentication and configuration sections: `https://learn.chatgpt.com/docs/auth.md` and `https://learn.chatgpt.com/docs/config-file/environment-variables.md`

- Anthropic Claude Code setup and authentication: `https://code.claude.com/docs/en/getting-started`

- Anthropic Claude Code CLI reference: `https://code.claude.com/docs/en/cli-usage`

Planning-time local observations must be re-probed before execution.

Local planning probes on 2026-07-16 observed Claude Code 2.1.211 and Codex CLI 0.144.5; these observations are not execution pins.

## 26. Immediate next actions after plan approval

1. Add this strategic amendment and its review document to planning PR #205; rerun the document/graph checks and merge when green.

2. Record a superseding roadmap amendment on issues #196, #203, and #204: native tools are primary, MCP mediation is secondary, and Tier 0 is separate from contributor acceptance.

3. Create the Claude and Codex Tier-0, native-boundary/E2E, efficiency, critical-scheduler, and distribution Beads; apply critical/contributor/post-launch labels and validate zero cycles.

4. Close PLAN-MR only after PR #205 merges and the planning worktree refreshes from merged `main`.

5. Register up to four primaries in each ready worktree through Agent Mail, post the file-ownership maps, and start W0/W1/W2/W3 critical tasks concurrently.

6. By 2026-07-18, finish provider/publication terms, #196 amendment, LAB/evaluator pin, native Claude feasibility, Tier-0 governance, claims calendar, and the first Jamie send/decline decision.

7. Target the reviewed Claude Tier-0 paired package by 2026-07-21 and its preliminary writeup/README refresh within 24 hours; target the nonblocking Codex Tier-0 follow-on by 2026-07-23, escalating on 2026-07-25.

8. Record John's exact-100 decision as immutable `launch_case_count=100`, complete source-universe classification, perform only the approved make-before-break official graph migration, and keep W1 on the parallel official-eval critical path.

9. Keep the current acquisition agent and live store uninterrupted; no labels or planning changes authorize a mid-stage refresh or second writer.

10. Report readiness from live `bd`, GitHub, workflow, artifact, registry, and publication state at every checkpoint and date escalation.

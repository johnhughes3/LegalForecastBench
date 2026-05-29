# Multi-Harness Community Benchmark: Plan

## Goal

Build a repo-owned multi-harness benchmark package that can run Harvey LAB and LegalForecastBench through comparable harness adapters, validate adapter conformance with first-class tests, and publish community submissions separately from official LegalForecastBench results while crediting Legal Quants, John Hughes (LegalForecastBench/codebase maintainer), harness authors, task-source authors, and community contributors clearly.

The implementation should be additive: preserve the protected official LegalForecastBench path, add a separate community/multi-harness package and publication surface, and make it easy for technically skilled lawyers to contribute adapters without becoming maintainers of this whole codebase.

## Background

### Up-front decisions from John

- Official LegalForecastBench results should remain separate from community multi-harness results; community results need their own presentation surface and tracking method rather than being mixed into the official benchmark page.
- The adapter boundary should be a repo-owned canonical adapter spec. The plan should not assume LAB's own CLI process is the orchestrator; this repo should own the orchestration needed to run LAB tasks or LegalForecastBench tasks through multiple harnesses, importing or wrapping LAB components where consistent with that goal.
- v1 should prefer a host-orchestrated runtime model: a CLI coordinates consistent Docker/Podman/sandbox policies across harnesses, with network disabled except for declared model-provider API egress where allowed.
- Public presentation should use two purpose-built frontends: one for official LegalForecastBench results and one for community multi-harness comparisons. The plan may choose GitHub, Hugging Face, or a hybrid for full artifact storage.

### Local evaluation seams

- LegalForecastBench already separates benchmark packet/prompt/scoring logic from harness-specific execution. `ModelPacket.to_record()` serializes benchmark packets in `legalforecast/evals/packet_builder.py:147`; `build_model_packet()` constructs packets from case packets, prediction units, texts, metadata, ablation, and docket constraints at `legalforecast/evals/packet_builder.py:167`.
- `legalforecast/evals/inspect_task.py` is the current neutral harness seam. `HarnessSolver` requires `solver_id`, `solver_kind`, and `solve(request)` at `legalforecast/evals/inspect_task.py:40`; `HarnessRequest` and `SolverResponse` sit at `legalforecast/evals/inspect_task.py:118` and `legalforecast/evals/inspect_task.py:126`; `run_inspect_fixture(samples, solvers)` emits run records at `legalforecast/evals/inspect_task.py:402`.
- Prompt rendering is repo-owned: `render_model_prompt()` emits the task, strict response contract, case metadata, prediction units, mounted documents, and tool payload at `legalforecast/evals/inspect_task.py:346`; `build_inspect_samples()` converts packets into deterministic samples at `legalforecast/evals/inspect_task.py:317`.
- Run artifacts flow through `InspectCaseRunResult.to_record()` at `legalforecast/evals/inspect_task.py:186`, then `parse_model_output()` at `legalforecast/evals/output_parser.py:208`, then `score_cases()` at `legalforecast/evals/scorers.py:227`, with accounting normalized by `accounting_records_from_harness_records()` at `legalforecast/evals/accounting.py:216`.
- The optional Inspect AI adapter is explicitly a dependency boundary rather than the benchmark owner: `build_headline_inspect_ai_task()` keeps LegalForecast in charge of packet construction, output parsing, accounting, and official Brier scoring at `legalforecast/evals/inspect_ai_adapter.py:181` and `legalforecast/evals/inspect_ai_adapter.py:196`.

### Local official publication and community constraints

- `.agents/AGENTS.md:11-16` says this benchmark is intentionally not adopting preregistration protocols or result-tier classifications such as `official / verified-community / community-unverified / alpha-non-canonical`; community submission language should avoid reintroducing that deprecated taxonomy.
- Official runs are deliberately protected. `.github/workflows/run-benchmark.yaml:3-55` is manual `workflow_dispatch`; `.github/workflows/run-benchmark.yaml:65-70` uses the protected `legalforecastbench-official-eval` environment; `.github/workflows/run-benchmark.yaml:107-112` restricts official evaluation to `refs/heads/main`; `.github/workflows/run-benchmark.yaml:143-181` fails closed when provider credentials/settings are missing.
- Official per-case artifacts are small and safe: `runs.jsonl`, `accounting.jsonl`, `metrics.json`, and `runner-log.jsonl` are written in `legalforecast/evals/per_case_runner.py:292-312`; public uploads are limited to `metrics/` and `reports/` at `legalforecast/evals/per_case_runner.py:319-348`.
- Official aggregation already produces a public/private split: public `scores.json`, `unit-scores.jsonl`, `cycle-power.json`, leaderboard JSON/CSV/MD/HTML, run cards, artifact indexes, and manifests are written in `legalforecast/publication/official_aggregate.py:214-270` and `legalforecast/publication/official_aggregate.py:859-890`; raw/debug outputs remain under `private-debug` at `legalforecast/publication/official_aggregate.py:200-208`.
- `publication_guardrails.py` blocks raw documents, private paths, secrets, and provider account IDs from public artifacts (`legalforecast/publication/publication_guardrails.py:16-100`), and official aggregation enforces those guardrails before publishing artifact manifests at `legalforecast/publication/official_aggregate.py:271-274`.
- Current reporting can already render static JSON/CSV/Markdown/HTML leaderboards: `BenchmarkLeaderboardReport` lives at `legalforecast/reporting/leaderboard.py:264-294`; renderers are at `legalforecast/reporting/leaderboard.py:281-403`.

### CLI, packaging, and testing seams

- `pyproject.toml:1-3` uses Hatchling; `pyproject.toml:5-21` defines the package as Python `>=3.12` with no runtime dependencies; `pyproject.toml:23-24` exposes one console script, `legalforecast = "legalforecast.cli:main"`; `pyproject.toml:49-52` keeps Pyright strict over `legalforecast` and `scripts`.
- CLI dispatch is centralized in `legalforecast/cli.py:214-224` and `legalforecast/cli.py:1125-1145`. Existing benchmark commands include `packet build`, `eval run`, `eval run-case`, `score`, `report`, and `fixture e2e` across `legalforecast/cli.py:340-425`.
- The local fixture path `_cmd_model_run()` reads packets, builds samples, runs `run_inspect_fixture`, and writes runs/accounting JSONL at `legalforecast/cli.py:1402-1460`; the isolated official shard path `_cmd_eval_run_case()` constructs `PerCaseRunnerConfig` and calls `run_per_case_evaluation()` at `legalforecast/cli.py:1463-1509`.
- Existing tests already cover the harness prompt/output boundary (`tests/test_inspect_task.py:32-105`), the Inspect adapter shim and injected factory path (`tests/test_inspect_ai_adapter.py:29-94`), adversarial/controlled docket behavior (`tests/test_harness_sandbox.py:35-104`), per-case safe output behavior (`tests/test_per_case_runner.py:29-94`), and protected official workflow shape (`tests/test_official_eval_matrix_workflow.py:9-147`).

### Prior art and deleted docs

- Current `docs/`, `docs/plans`, and `docs/completed` were absent before this plan; historical docs were removed in `774d800d4de2b3bdb557c88d799af79597b4904d` (`chore: prepare public repository`).
- Deleted `774d800^:docs/official_aggregation.md` described official matrix validation, public/private artifact boundaries, leaderboard outputs, run cards, artifact indexes, and manifest expectations. The current code still reflects much of that machinery in `legalforecast/publication/official_aggregate.py` and related tests.
- Deleted `774d800^:docs/result_tiers.md` sketched a community submission bundle and review path, but it used the result-tier taxonomy now marked deprecated in `.agents/AGENTS.md:11-16`; reuse artifact ideas, not the tier labels.

### Harvey LAB seams

- Harvey LAB current `main` was observed at commit `b4b960e4bd4471553c324d82bf5457bc017cbdf2` on 2026-05-29. It is an MIT-licensed public repo at <https://github.com/harveyai/harvey-labs/>.
- LAB's `pyproject.toml` requires Python `>=3.12,<3.14`, includes provider SDK dependencies, and notes an out-of-band Pandoc CLI requirement for document extraction (<https://github.com/harveyai/harvey-labs/blob/b4b960e4bd4471553c324d82bf5457bc017cbdf2/pyproject.toml#L294-L321>).
- LAB is filesystem/CLI-first: tasks live under `tasks/`, runs under `results/`, reports are static HTML, and invocation is `uv run python -m harness.run` (<https://github.com/harveyai/harvey-labs/blob/b4b960e4bd4471553c324d82bf5457bc017cbdf2/docs/architecture.md#L237-L265>).
- LAB task directories contain `task.json` and `documents/`; `harness/run.py` resolves task IDs under `BENCH_ROOT / "tasks"` and requires `task.json` plus `documents/` (<https://github.com/harveyai/harvey-labs/blob/b4b960e4bd4471553c324d82bf5457bc017cbdf2/harness/run.py#L1009-L1049>).
- LAB's adapter interface normalizes a provider chat loop around `chat(messages, tools)`, provider-specific message builders, `ToolCall`, and `ModelResponse`; its agent loop stops when the model stops calling tools. Its built-in tools are `bash`, `read`, `write`, `edit`, `glob`, and `grep`.
- LAB evaluation is rubric/judge-based. `evaluation.run_eval` evaluates criteria independently, emits `scores.json`, and writes `report.html`; task-level score is all-pass, while criteria-level fields preserve diagnostics.
- LAB's sandbox assumes Podman and a canonical `/workspace` layout: `/workspace` read-write, `/workspace/documents` read-only, `/workspace/output` read-write, with isolation flags including `--network=none`, `--cap-drop=ALL`, and `--user uid:gid` (<https://github.com/harveyai/harvey-labs/blob/b4b960e4bd4471553c324d82bf5457bc017cbdf2/sandbox/README.md#L260-L299>).

### External harness and provider facts

- LQ.AI is the LegalQuants open-source, self-hosted legal AI platform: bring-your-own keys, run on laptop/internal server/cloud VM, own the data, and choose Anthropic, OpenAI, Azure OpenAI, or local Ollama out of the box (<https://github.com/LegalQuants/lq-ai>; README lines 1-4). Its relevant harness features are matter-scoped projects, inspectable skills, citation verification, anonymization, audit logs, inference-tier awareness, Docker Compose deployment, and a broader LegalQuants ecosystem posture of open, citation-grounded, attorney-attested legal-AI tooling (<https://raw.githubusercontent.com/LegalQuants/lq-ai/main/README.md>).
- Hermes Agent is now a concrete target: the docs describe Nous Research’s Hermes Agent as a self-improving agent with installable CLI, persistent memory/skills, MCP support, 20+ messaging platforms, 60+ tools, and terminal backends including local, Docker, SSH, Daytona, Singularity, and Modal (<https://hermes-agent.nousresearch.com/docs/>). Its architecture docs identify CLI, Gateway, ACP, Batch Runner, API Server, and Python Library entry points, centered on `AIAgent`, provider resolution, tool dispatch, SQLite/FTS5 session storage, and 70+ tools across about 28 toolsets (<https://hermes-agent.nousresearch.com/docs/developer-guide/architecture>).
- OpenClaw has an explicit agent harness plugin surface: a harness is the low-level executor for one prepared OpenClaw agent turn, while OpenClaw core still owns provider/model resolution, auth state, thinking/context budget, transcript, workspace, sandbox, tool policy, delivery callbacks, fallback policy, and observability (<https://docs.openclaw.ai/plugins/sdk-agent-harness>). The docs say the harness surface is for bundled or trusted native plugins and remains experimental, but also document a bundled native Codex harness path and strict runtime selection/fail-closed behavior.
- OpenAI’s Codex loop uses the Responses API for inference and exposes a Responses-shaped agent loop with tool definitions, streaming events, reasoning/tool-call items, and optional `previous_response_id` semantics (<https://openai.com/index/unrolling-the-codex-agent-loop/>; <https://developers.openai.com/api/reference/resources/responses/methods/create>). Treat this as a provider/runtime baseline and as part of the OpenClaw/Codex comparison, not a substitute for LQ.AI/Hermes/OpenClaw first-class adapters.
- Claude Agent SDK is a Python/TypeScript library that exposes Claude Code’s tools, agent loop, and context management for local infrastructure, but Anthropic disallows third-party developers from offering `claude.ai` login or subscription rate limits unless approved; API-key auth should be assumed (<https://code.claude.com/docs/en/agent-sdk/overview>).
- Hugging Face Datasets can host versioned dataset repositories with dataset cards and web/programmatic uploads (<https://huggingface.co/docs/hub/en/datasets-adding>), while GitHub Pages can publish static sites from Actions or a configured branch/folder (<https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site>).

## Approach

### 1. Add an isolated `legalforecast/multiharness/` package

Build the multi-harness system as an additive package under `legalforecast/multiharness/`, not as a rewrite of `legalforecast/evals/inspect_task.py` or the protected official workflows. The new package owns canonical multi-harness concepts: tasks, task indexes, adapter capabilities, run requests, run results, sandbox policies, conformance reports, community submissions, and community aggregates.

Keep existing `legalforecast/evals/*` modules as the source of truth for LegalForecastBench packet construction, prompts, output parsing, scoring, and accounting. The multi-harness layer should project into and out of those existing contracts rather than duplicating legal benchmark logic.

Recommended initial package boundary:

```text
legalforecast/multiharness/
  __init__.py
  spec.py
  validation.py
  task_loaders.py
  selection.py
  adapters.py
  builtin_adapters.py
  command_adapter.py
  sandbox.py
  runner.py
  conformance.py
  artifacts.py
  community.py
  reporting.py
```

### 2. Define canonical task families rather than canonicalizing metrics away

The same runner should schedule both LegalForecastBench and Harvey LAB tasks, but reports must not pretend the metrics are comparable. LegalForecastBench produces probability forecasts scored by Brier/log-loss/calibration metrics; LAB produces task/deliverable outputs judged against rubric criteria. The canonical layer should normalize orchestration, provenance, artifacts, and adapter behavior, while keeping suite-specific scoring modes separate.

Use explicit task-family and scoring-mode concepts:

- `legalforecast_mtd` + `lfb_brier`
- `harvey_lab` + `lab_native`
- `contract_only` only for conformance/smoke tests, not headline community comparisons

Community tables should group rows by `(family, scoring_mode, selection_sha256)`. Do not compute a single cross-suite winner.

### 3. Make the command adapter the public contribution surface

The Python in-process protocol is useful for built-ins, but external contributors should not have to package Python modules into this repository. The public adapter extension point should be a JSON `adapter.json` plus a command protocol:

- `capabilities --output capabilities.json`
- `run --request request.json --output result.json --workspace workspace-dir`

The host never invokes adapters through `shell=True`; commands are argv arrays; adapter stdout/stderr stay private unless explicitly summarized. This gives technically skilled lawyers a simple path: write a script/CLI that reads one JSON request and writes one JSON result, then run the conformance suite.

### 4. Use host-owned sandbox policy, not nested-container assumptions

v1 should use a host-orchestrated policy object that can build Docker/Podman plans and keep tool containers network-disabled. Provider calls should happen from the host adapter process under declared env vars; the tool sandbox should not have general network access by default. This mirrors the user’s goal of consistent environments while avoiding Docker-in-Docker or LAB-in-LFB container nesting as a baseline assumption.

The policy should serialize to `sandbox.plan.json` for every run, including backend, image, mounts, UID/GID behavior, network mode, capabilities, no-new-privileges, resource limits, and timeout.

### 5. Integrate Harvey LAB first as a pinned/local CLI bridge

Treat LAB as a dependency/test corpus/harness source, not as the controlling process. For v1, prefer a controlled subprocess bridge to a pinned or user-supplied LAB checkout rather than vendoring LAB or importing unstable internals. The bridge should scan LAB `tasks/**/task.json` into canonical task records, materialize selected tasks into a temporary LAB-compatible layout, run LAB’s command where possible, collect native LAB artifacts, and normalize LAB `scores.json` into community report rows.

Implementation must verify LAB CLI flags against the pinned commit before enabling real LAB execution. If LAB lacks a stable flag for bench root/output root, the adapter should fail with a clear error and require a LAB command manifest until the bridge is updated.

### 6. Keep official and community publication separate by construction

Do not extend `official_aggregate.py` to ingest community results. Add a separate community submission and aggregation path. Official LegalForecastBench results remain protected by main-branch workflows, S3/OIDC boundaries, official aggregation, and official public/private artifact rules. Community multi-harness comparisons get their own schema, validation workflow, generated site, and artifact storage rules.

Recommended v1 storage/publication model:

- GitHub PRs are canonical for small metadata submissions and review history.
- Large run bundles live outside git as immutable artifacts, preferably Hugging Face Dataset revisions or GitHub Release assets, referenced by URL and SHA-256.
- A generated static community site renders accepted submissions and comparison tables.
- A separate generated static official site renders official LegalForecastBench results.

### 7. Use “provenance and presentation surfaces,” not deprecated result tiers

Avoid `result_tier`, `verified-community`, `community-unverified`, and similar labels. Community submissions can still have validation state, conformance state, artifact hashes, and maintainer review status, but those should be operational provenance fields, not benchmark result tiers.

Each row should credit:

- LegalForecastBench / John Hughes / Legal Quants for the benchmark infrastructure
- Harvey LAB where LAB tasks are used
- Adapter authors
- Submission authors/runners
- Model/provider identity as reported by the submission

Working public names pending final approval:

- **LegalForecastBench Official Results**
- **LegalForecastBench Community Harness Comparisons**

### 8. Make LQ.AI, Hermes Agent, and OpenClaw first-class harness targets

Do not let any one external harness block the core spec, but do treat LQ.AI, Hermes Agent, and OpenClaw as first-class adapter tracks rather than optional “maybe later” pilots. The foundation still comes first — schemas, command adapter, conformance, runner, publication — because those make each external integration testable and comparable. After that foundation exists, the first-class tracks should proceed in parallel where possible:

1. **LQ.AI adapter track:** run LAB or LFB tasks through a self-hosted LQ.AI deployment using its gateway/API or a command-manifest bridge; record project/matter scope, inference tier, provider route, anonymization setting, citation-verification behavior, audit-log correlation ID, and skill/playbook context used for the run.
2. **Hermes Agent adapter track:** run LAB or LFB tasks through a Hermes CLI, batch runner, API server, or Python-library entry point; isolate `HERMES_HOME`/profile per run; record model/provider resolution, enabled toolsets, terminal backend, memory/session policy, MCP servers, and trajectory/session export references.
3. **OpenClaw adapter track:** run LAB or LFB tasks through OpenClaw’s harness/plugin model, preferably as a command adapter first and then as a native trusted plugin if needed; record provider/model route, harness ID, runtimePlan/tool policy, transcript mirror, selected native runtime, and fail-closed proof when a required harness is unavailable.
4. **Provider/runtime baselines:** keep OpenAI Responses/Codex-style and Claude Agent SDK adapters as useful baselines for interpreting the proprietary/open-source harness gap, with API-key auth and explicit provider-terms assumptions.

For user-owned subscriptions/CLIs, the plan should permit command adapters that call a user-installed CLI when that use is allowed by the tool/provider terms, but each adapter must record auth mode and terms assumptions. The project should not claim that ChatGPT/Claude subscriptions are a general third-party API entitlement.

### 9. Use GitHub as the reviewed registry and Hugging Face as the artifact/data mirror

Community runs should auto-appear on the community site after validation, but not through an unauthenticated “upload into production” service. Use a two-layer registry:

1. **GitHub registry of record:** accepted submission metadata lives as reviewed files under `community/submissions/**` plus generated indexes under `community/registry/**`. A pull request is the audit trail, attribution mechanism, validation gate, and moderation point. On merge to `main`, a GitHub Actions workflow rebuilds the community aggregate and deploys the static community site.
2. **Hugging Face dataset mirror for large artifacts:** full run bundles, Parquet/JSONL rollup tables, transcripts allowed for public release, and larger per-task artifacts can live in a LegalForecastBench or LegalQuants Hugging Face Dataset repository. Submission manifests reference immutable HF revisions or file URLs plus SHA-256 hashes. HF is not the sole source of truth for acceptance; GitHub records what was accepted and how it was attributed.
3. **Optional later inbox:** a small upload portal or bot can later create GitHub PRs and/or HF upload PRs on behalf of users, but v1 should avoid a custom database service. The “database” is versioned JSON/JSONL/Parquet plus artifact hashes, rebuilt into site data on every accepted change.

Partial runs are first-class submissions. Each submission records `selection_sha256`, `selection_label`, source suite/version, task IDs, folder/module/practice-area selectors, adapter ID/version, model key, sandbox policy hash, and run config hash. The community aggregator can then:

- show partial submissions as honest partial coverage;
- merge compatible shards into a “composite community run” only when they share suite version, adapter version, model key, sandbox policy hash, scoring mode, and non-overlapping task IDs;
- show coverage matrices by LAB folder/practice area and LFB subset;
- credit each shard contributor separately, including when one person runs a LAB folder and another person later contributes the same harness/model/config on a different folder.

## Work Items

### Item 1 — Canonical multi-harness schemas

**Goal:** Add the repo-owned schema layer for canonical tasks, adapter capabilities, run requests/results, sandbox policies, artifact records, contributor credits, conformance reports, and community submissions.

**Done when:**

- `legalforecast/multiharness/spec.py`, `validation.py`, and `__init__.py` exist and import without Docker, LAB, provider SDKs, or network access.
- Schema versions are explicit for task, task index, adapter manifest, adapter capabilities, sandbox policy, run request, run result, run manifest, conformance report, community submission, and community aggregate.
- Validators reject invalid schema versions, unsafe paths, malformed hashes, duplicate IDs, secret-like public fields, and deprecated result-tier fields.
- `tests/test_multiharness_spec.py` covers serialization round-trips and validation failures.

**Key files:**

- New: `legalforecast/multiharness/spec.py`
- New: `legalforecast/multiharness/validation.py`
- New: `legalforecast/multiharness/__init__.py`
- New: `tests/test_multiharness_spec.py`
- Existing references: `legalforecast/publication/run_cards.py`, `legalforecast/publication/official_aggregate.py`, `legalforecast/publication/publication_guardrails.py`

**Dependencies:** None.

**Size:** M.

### Item 2 — Task loaders for LegalForecastBench and Harvey LAB

**Goal:** Convert LegalForecastBench packet records and Harvey LAB task directories into a shared `TaskIndex` while preserving suite-specific metadata and scoring modes.

**Done when:**

- `LfbTaskLoader` converts LFB packet JSONL or run-input manifest rows into canonical tasks using existing `ModelPacket` reconstruction and `build_inspect_samples()`.
- LFB canonical tasks preserve candidate/case/ablation metadata, required unit IDs, prompt hash, packet hash, and document hashes without exposing model packets in public summaries.
- `HarveyLabTaskLoader` scans `tasks/**/task.json` plus `documents/` under a LAB checkout, records LAB commit when available, hashes task JSON and documents, and infers module/practice area from task metadata or path segments.
- Missing LAB `task.json` or `documents/` fails deterministically before execution.
- `tests/test_multiharness_task_loaders.py` covers LFB fixtures, LAB fixtures, path normalization, hashing, missing documents, and LAB metadata inference.

**Key files:**

- New: `legalforecast/multiharness/task_loaders.py`
- New: `tests/test_multiharness_task_loaders.py`
- Existing: `legalforecast/evals/packet_builder.py:147`, `legalforecast/evals/packet_builder.py:167`, `legalforecast/evals/inspect_task.py:317`, `legalforecast/evals/inspect_task.py:346`
- External: Harvey LAB `tasks/**/task.json`, `documents/`, `harness/run.py`

**Dependencies:** Item 1.

**Size:** L.

### Item 3 — Deterministic task selection and partial-run support

**Goal:** Let contributors run a full benchmark, a LAB module/practice area, selected LAB tasks, selected LFB cases/ablations, or a deterministic sampled subset.

**Done when:**

- `TaskSelection` supports filters for suite/family, task IDs, case IDs, candidate IDs, ablations, modules, practice areas, tags, limit, and seed.
- Selection is deterministic and computes `selection_sha256` over selected canonical task records.
- Empty selections fail unless explicitly allowed.
- Community reports compare rows only within the same `(family, scoring_mode, selection_sha256)` group.
- `tests/test_multiharness_selection.py` covers LFB filters, LAB filters, tag filters, duplicate selector handling, deterministic seed/limit behavior, and empty selection failure.

**Key files:**

- New: `legalforecast/multiharness/selection.py`
- New: `tests/test_multiharness_selection.py`
- Existing references: `legalforecast/evals/per_case_runner.py:389-447`, `legalforecast/publication/official_aggregate.py:443-540`

**Dependencies:** Items 1–2.

**Size:** M.

### Item 4 — Host-owned sandbox policy planner

**Goal:** Define a consistent Docker/Podman execution policy that every adapter can declare and every run can serialize, without requiring nested containers or networked tool sandboxes in v1.

**Done when:**

- `SandboxPolicy` records backend, image, network policy, mounts, working directory, UID/GID behavior, cap-drop, no-new-privileges, PID/memory/CPU limits, timeout, and allowed provider env var names.
- Docker and Podman command builders produce dry-run plans with `--network=none`, hardening flags, path-safe mounts, and platform-specific warnings.
- `PROVIDER_EGRESS_HOST_ONLY` keeps tool containers network-disabled while permitting provider calls only in host adapter processes.
- Missing container backends fail before scheduling live rows.
- `tests/test_multiharness_sandbox.py` covers Docker/Podman plan generation, network-disabled defaults, provider-egress behavior, mount safety, timeout handling, and no dependency on Docker/Podman being installed.

**Key files:**

- New: `legalforecast/multiharness/sandbox.py`
- New: `tests/test_multiharness_sandbox.py`
- Existing reference: `tests/test_harness_sandbox.py:35-104`
- External reference: Harvey LAB sandbox README at pinned commit

**Dependencies:** Item 1.

**Size:** M.

### Item 5 — Adapter protocol and language-agnostic command adapter

**Goal:** Provide the extension surface community contributors will actually use: a manifest plus CLI command protocol, with safe subprocess execution and result validation.

**Done when:**

- `HarnessAdapter` protocol defines capabilities, prepare, and run phases for in-process adapters.
- `CommandAdapterManifest` supports adapter ID, display name, version, argv-array command, and contributor credits.
- The command protocol supports `capabilities --output capabilities.json` and `run --request request.json --output result.json --workspace workspace-dir`.
- Subprocess execution never uses `shell=True`, captures stdout/stderr privately, enforces timeout, and validates result/artifact paths.
- `tests/test_multiharness_command_adapter.py` covers manifest validation, relative command resolution, capabilities loading, run invocation, timeout/error behavior, unsafe artifact rejection, and private log handling.

**Key files:**

- New: `legalforecast/multiharness/adapters.py`
- New: `legalforecast/multiharness/command_adapter.py`
- New: `tests/test_multiharness_command_adapter.py`

**Dependencies:** Items 1 and 4.

**Size:** L.

### Item 6 — Built-in LFB native adapter and projection layer

**Goal:** Prove the canonical multi-harness contract can run LegalForecastBench tasks while reusing existing packet, prompt, parser, scoring, and accounting code.

**Done when:**

- `LfbNativeAdapter` supports LFB canonical tasks in offline fixture mode using existing `build_inspect_samples()` and `run_inspect_fixture()`.
- `LfbNativeAdapter` live model mode is out of scope for this item; live/provider comparisons should use external adapters or the existing protected official path. No new provider logic is added here.
- `artifacts.py` projects successful LFB `AdapterRunResult` rows into inspect-compatible records consumed by existing parser/accounting/scoring paths.
- The LFB projection pins the required field set rather than leaving it implicit: `sample_id`, `candidate_id`, `case_id`, `related_family_id`, `mdl_family_id`, `solver_id`, `solver_kind`, `run_label`, `ablation`, `raw_output`, `raw_output_sha256`, `required_unit_ids`, `request_count`, `input_tokens`/`prompt_tokens`, `output_tokens`/`completion_tokens`, `estimated_total_tokens`, `estimated_cost`, `tool_call_logs`, `metadata`, `execution_backend`, provider/model identifiers when known, and latency fields when known.
- Community model identity includes adapter and model, e.g. `{adapter_id}:{model_key}`, without changing official `ScoreSummary` behavior.
- `tests/test_multiharness_runner.py` or a dedicated projection test confirms LFB adapter output can be parsed, accounted, and scored with existing code.

**Key files:**

- New: `legalforecast/multiharness/builtin_adapters.py`
- New: `legalforecast/multiharness/artifacts.py`
- Existing: `legalforecast/evals/inspect_task.py:40`, `legalforecast/evals/inspect_task.py:402`, `legalforecast/evals/output_parser.py:208`, `legalforecast/evals/scorers.py:227`, `legalforecast/evals/accounting.py:216`
- Tests: `tests/test_inspect_task.py`, new projection/runner tests

**Dependencies:** Items 1–5.

**Size:** M.

### Item 7 — Adapter conformance suite for contributors

**Goal:** Make it straightforward for a lawyer or external developer to verify a new adapter before submitting it.

**Done when:**

- `legalforecast multiharness conformance --adapter-manifest path/to/adapter.json --output-dir tmp/conformance` runs without provider credentials by default.
- The suite produces `conformance-report.json`, `conformance-report.md`, `adapter-capabilities.json`, fixture results, and sandbox negative-control artifacts.
- Checks include manifest validation, capabilities validation, LFB fixture run, LAB fixture run if declared, sandbox-policy receipt, public-safety scan, idempotent resume behavior, and actionable error messages.
- Markdown output explains failures in plain English and points to the adapter spec.
- `tests/test_multiharness_conformance.py` covers a passing fixture adapter and several broken adapters.

**Key files:**

- New: `legalforecast/multiharness/conformance.py`
- New: `tests/test_multiharness_conformance.py`
- Existing: `legalforecast/publication/publication_guardrails.py:145-171`

**Dependencies:** Items 1–6.

**Size:** L.

### Item 8 — Multi-harness runner

**Goal:** Schedule selected tasks across compatible adapters and models, execute them in isolated workspaces, and write deterministic canonical run artifacts.

**Done when:**

- `MultiHarnessRunConfig` accepts a task index, selection, adapters, model configs, sandbox policy, output dir, max parallelism, resume flag, and incomplete-run policy.
- The runner validates task index, selection, adapter capabilities, model modes, and sandbox policy before starting any row.
- It writes `run-manifest.json` before execution; per row it writes `request.json`, `sandbox.plan.json`, `result.json`, private logs, and canonical `canonical-runs.jsonl` in deterministic matrix order.
- Deterministic row IDs use `sha256(family + task_id + adapter_id + adapter_version + model_key + selection_sha256)[:16]`; the full `request_hash` separately covers the serialized run request, including sandbox policy, model config, adapter capabilities hash, and task record hash.
- It projects LFB rows into `lfb/runs.jsonl` and LAB rows into `lab/task-results.jsonl`.
- `--resume` skips rows only when existing results validate and the existing `request_hash` matches the current serialized request.
- Sequential execution is stable before bounded concurrency is added.
- `tests/test_multiharness_runner.py` covers matrix compatibility, deterministic run IDs, resume, failure rows, artifact indexes, LFB projection, and LAB separation.

**Key files:**

- New: `legalforecast/multiharness/runner.py`
- New: `tests/test_multiharness_runner.py`
- Existing reference: `legalforecast/evals/per_case_runner.py:191-370`

**Dependencies:** Items 1–7.

**Size:** L.

### Item 9 — Harvey LAB CLI bridge adapter

**Goal:** Run selected LAB tasks through a controlled local/pinned LAB checkout and normalize native LAB outputs into canonical community artifacts.

**Done when:**

- `HarveyLabCliAdapter` accepts `--lab-root` or `HARVEY_LAB_ROOT`, validates the LAB checkout, records commit and task hashes, and materializes selected tasks into a temporary LAB-compatible layout.
- The adapter writes a `lab-command-capabilities.json` probe before attempting real execution: LAB commit, `uv run python -m harness.run --help` output hash, supported task/output/root flags, supported evaluation command, sandbox backend expectation, and any missing capabilities. If the needed bench-root/output flags are unavailable, it fails with a clear message and records the blocker.
- Native LAB `scores.json` is parsed into criterion-level and task-level LAB summary records.
- LAB `report.html` and transcripts are treated as private artifacts unless a later publication step explicitly includes guardrail-approved summaries.
- CI tests use a fixture LAB command rather than requiring a real LAB checkout, Docker/Podman, provider credentials, or network.
- Optional live integration tests are documented and gated by an explicit env var.

**Key files:**

- New/modified: `legalforecast/multiharness/builtin_adapters.py`
- New tests: LAB fixture command under `tests/fixtures/multiharness/`, `tests/test_harvey_lab_adapter.py` or included in runner tests
- External: Harvey LAB `harness/run.py`, `evaluation/run_eval.py`, `sandbox/README.md`, `tasks/**/task.json`

**Dependencies:** Items 1–8.

**Size:** L.

### Item 10 — CLI command group

**Goal:** Expose the multi-harness package through the existing `legalforecast` CLI without breaking current commands or official workflows.

**Done when:**

- `legalforecast multiharness` appears in top-level help.
- Subcommands exist for `tasks index`, `tasks select`, `adapters inspect`, `conformance`, `run`, `report`, `community package`, `community validate-submission`, `community aggregate`, and optional `community upload-artifacts`/`community open-pr` helpers if those can be implemented without storing maintainer credentials.
- Dry-run commands write stable plan JSON and do not run adapters/containers.
- CLI handlers remain thin wrappers around `legalforecast/multiharness/*` library functions.
- Existing CLI aliases and official commands continue to pass current tests.
- `tests/test_multiharness_cli.py` covers help output, dry-run plans, task indexing/selection, conformance invocation, and a synthetic run.

**Key files:**

- Modified: `legalforecast/cli.py:214-425`, `legalforecast/cli.py:1125-1145`
- New: `tests/test_multiharness_cli.py`
- Existing: `tests/test_cli_orchestration.py`

**Dependencies:** Items 1–8; Item 9 may be optional behind `--lab-root` until stabilized.

**Size:** L.

### Item 11 — Community submission schema and validation

**Goal:** Define how community results are submitted, credited, checked, and kept separate from official LegalForecastBench outputs.

**Done when:**

- `CommunitySubmissionManifest` validates submission ID, submitter, contributors, benchmark credit, run summary, artifact references, SHA-256 hashes, and attestations.
- Required attestations include: not an official LegalForecastBench result, no private/sealed material in public artifacts, right to submit artifacts, and provider terms acknowledged.
- Banned fields such as `result_tier`, `verified-community`, `community-unverified`, and `alpha-non-canonical` fail validation.
- v1 intake path is PR metadata under `community/submissions/<year>/<submission_id>/`, with large artifacts referenced by immutable URL plus SHA-256 rather than committed wholesale.
- `legalforecast multiharness community package` turns a local run directory into a PR-ready submission folder containing `submission.json`, `public-summary.json`, `conformance-report.json`, `selection-manifest.json`, and an artifact manifest; it can also produce a `hf-upload-plan.json` for users who want to mirror large artifacts to a Hugging Face Dataset repo.
- Submission manifests support partial-run shards: `selection_sha256`, `selection_label`, source suite/version, task selectors, explicit task IDs, adapter ID/version, model key, sandbox policy hash, run config hash, shard ID, compatible-shard group ID, and contributor credit per shard.
- Attribution distinguishes run submitter, run operator, adapter author, task-source credit, benchmark/infrastructure credit, and optional compute sponsor; GitHub handle, Hugging Face handle, ORCID, institution, and URL are optional but supported.
- `tests/test_community_submission.py` covers valid submissions, missing attestations, hash mismatch, unsafe paths, deprecated taxonomy fields, shard compatibility fields, and contributor-credit requirements.

**Key files:**

- New: `legalforecast/multiharness/community.py`
- New: `community/submissions/.gitkeep`
- New: `tests/test_community_submission.py`
- Existing: `.agents/AGENTS.md:11-16`, `legalforecast/publication/publication_guardrails.py:16-100`

**Dependencies:** Items 1, 7, and 8.

**Size:** M.

### Item 12 — Community aggregation and static comparison site

**Goal:** Build the separate public surface for community multi-harness comparisons, using accepted submission metadata and safe public summaries.

**Done when:**

- `legalforecast/publication/community_aggregate.py` reads validated submissions, verifies local/referenced artifacts and hashes where available, runs guardrails over public summaries, groups by `(family, scoring_mode, selection_sha256)`, and writes a community public bundle.
- The aggregate writes a versioned flat-file registry under `community/registry/`: normalized submissions JSONL, task-coverage JSONL, contributor index JSON, adapter/model index JSON, compatible-shard groups, and site-ready summary JSON. This is the v1 “database.”
- Community outputs include JSON, CSV, Markdown, and HTML comparison reports; per-submission public JSON; artifact index; and artifact manifest.
- LAB and LFB metrics render in separate sections with plain-English metric explanations, plus coverage matrices by LAB folder/practice area and LFB subset.
- Compatible partial shards can roll up into composite rows only when suite version, scoring mode, selection namespace, adapter ID/version, model key, sandbox policy hash, run config hash, and task schema hash match and task IDs do not overlap. Composite rows must credit each shard contributor separately and link back to every underlying submission.
- Every row includes contributor credit, adapter credit, task-source credit, benchmark credit, conformance status, selection metadata, coverage percentage, shard/composite status, and artifact references.
- Public outputs omit raw model outputs, private logs, sealed/private source material, provider account IDs, and secrets.
- `tests/test_community_publication.py` covers aggregation, metric grouping, public/private separation, guardrail failures, contributor credits, and non-use of official aggregation.

**Key files:**

- New: `legalforecast/publication/community_aggregate.py`
- New/modified: `legalforecast/multiharness/reporting.py`
- New: `tests/test_community_publication.py`
- Existing: `legalforecast/reporting/leaderboard.py:264-403`, `legalforecast/publication/publication_guardrails.py:145-171`

**Dependencies:** Items 1–11.

**Size:** L.

### Item 13 — Official and community website generation

**Goal:** Produce two polished static public-facing sites as publication artifacts, without making a frontend framework or bespoke web app a prerequisite for validating community submissions.

**Done when:**

- Official site generation consumes existing official aggregate public artifacts and renders **LegalForecastBench Official Results** with official-only copy, run cards, methodology links, score tables, calibration/Pareto sections where available, and links to downloadable public artifacts.
- Community site generation consumes community aggregate artifacts and renders **LegalForecastBench Community Harness Comparisons** with separate LAB/LFB sections, adapter/conformance cards, contributor credits, selection filters, coverage matrices, shard/composite run views, artifact links, and clear non-official disclaimers.
- Static HTML/CSS is generated by Python renderers in v1; a later Next.js/Cloudflare/Vercel site can replace the renderer if the static pages prove valuable.
- Publication guardrails run over generated site outputs before artifact manifests are finalized.
- Tests verify official and community site outputs do not cross-link in a way that confuses official/community status.

**Key files:**

- New: `legalforecast/publication/site.py` or `legalforecast/publication/official_site.py`
- New/modified: `legalforecast/publication/community_aggregate.py`
- New/modified: `legalforecast/multiharness/reporting.py`
- Existing: `legalforecast/reporting/leaderboard.py:361-403`, `legalforecast/publication/official_aggregate.py:214-270`
- New tests: `tests/test_public_sites.py` or folded into community/official publication tests

**Dependencies:** Items 11–12 and existing official aggregate artifacts.

**Size:** L.

### Item 14 — Community validation workflow

**Goal:** Let GitHub validate community submission PRs and multi-harness changes without touching official secrets, official S3, or protected official environments.

**Done when:**

- `.github/workflows/community-multiharness-validation.yaml` runs on PRs touching `community/submissions/**`, `legalforecast/multiharness/**`, community publication code, docs, and tests.
- Workflow uses `permissions: contents: read`, no `id-token: write`, no AWS credentials, no provider secrets, and no `legalforecastbench-official-eval` environment.
- Workflow runs format/lint/typecheck/tests relevant to multi-harness and community validation, plus guardrail scans and community aggregate dry-run.
- On merge to `main`, a separate publish job rebuilds `community/registry/**`, regenerates the community site, and deploys it through the repository’s normal static-site deployment path without provider secrets or official benchmark credentials.
- Workflow tests assert no official environment, OIDC, AWS credentials, or provider secrets are referenced.

**Key files:**

- New: `.github/workflows/community-multiharness-validation.yaml`
- New: `tests/test_community_multiharness_workflow.py`
- Existing references: `.github/workflows/run-benchmark.yaml`, `.github/workflows/official-s3-access-validation.yaml`, `tests/test_official_eval_matrix_workflow.py`, `tests/test_official_s3_workflow.py`

**Dependencies:** Items 10–12.

**Size:** M.

### Item 15 — Contributor-facing docs and examples

**Goal:** Make adapter and submission contribution accessible to lawyers with technical skill while preserving academic/community credit norms.

**Done when:**

- `docs/multiharness-adapter-spec.md` documents the canonical schemas, adapter manifest, command protocol, sandbox policy, conformance command, example fixture adapter, troubleshooting, and provider-auth expectations.
- `docs/community-submissions.md` documents the PR intake path, optional Hugging Face Dataset artifact mirror, large-artifact storage guidance, partial-run shard/composite semantics, required attestations, contributor credits, benchmark/task-source attribution, and public/non-official disclaimers.
- `README.md` adds a short pointer to official results and community multi-harness comparisons without changing official benchmark positioning, including installation instructions once tagged packages are published.
- Docs include a minimal “run just one LAB module” example, “run just one LFB subset” example, and “add your favorite adapter” example.
- Docs say Harvey LAB is credited to Harvey and used under its license; final branding/naming remains subject to John/Legal Quants approval.

**Key files:**

- New: `docs/multiharness-adapter-spec.md`
- New: `docs/community-submissions.md`
- Modified: `README.md`
- Existing: `CITATION.cff`, `LICENSE`

**Dependencies:** Items 1–14.

**Size:** M.

### Item 16 — Release-check integration, package publication, and no-network smoke tests

**Goal:** Ensure the new system is part of normal quality gates and that tagged releases publish an installable runner package, without making routine release checks depend on LAB, Docker/Podman, provider credentials, or network.

**Done when:**

- `scripts/release_check.py` adds no-network smoke checks for canonical schema validation, task indexing, conformance fixture adapter, `multiharness run --dry-run`, and community aggregate dry-run.
- Release check does not require a real Harvey LAB checkout, Docker, Podman, Hugging Face credentials, GitHub credentials, provider keys, or external network.
- Existing release artifact contract tests still pass.
- A tag-triggered package publication workflow builds the Python package and publishes it to the chosen package registry (PyPI or GitHub Packages/TestPyPI first), so community members can install the `legalforecast` CLI without cloning the repo.
- The publish workflow runs only after release checks pass, uses trusted publishing or short-lived credentials where possible, and records package artifact hashes in release metadata.
- The documented pre-submit order remains `ruff format --check`, `ruff check`, `pyright`, `pytest`, and release check.

**Key files:**

- Modified: `scripts/release_check.py`
- New: `.github/workflows/publish-package.yaml` or an equivalent tag-triggered publish workflow
- Existing: `tests/test_release_check.py`, `tests/test_release_artifact_contract.py`
- New or modified tests as needed for release-check output

**Dependencies:** Items 1–15.

**Size:** M.

### Item 17 — First-class external harness adapter tracks: LQ.AI, Hermes Agent, and OpenClaw

**Goal:** Add first-class adapter support for LQ.AI, Hermes Agent, and OpenClaw so community runs can compare Harvey LAB and LegalForecastBench across a LegalQuants self-hosted legal-AI stack, a Nous Research autonomous-agent stack, and a SOTA open-source harness/plugin stack.

**Done when:**

- **LQ.AI:** A command-manifest or in-process adapter can run at least one LFB fixture and one LAB fixture through a local/self-hosted LQ.AI deployment or documented fixture bridge; conformance records LQ.AI version/commit, gateway/API route, project or matter scope, inference tier, provider route, anonymization setting, citation-verification setting, audit-log correlation ID, and skill/playbook context. The adapter must not require privileged official benchmark infrastructure or store provider secrets in artifacts.
- **Hermes Agent:** A command-manifest or in-process adapter can run at least one LFB fixture and one LAB fixture through Hermes CLI, batch runner, API server, or Python-library entry point; conformance records Hermes version/commit, `HERMES_HOME`/profile isolation, provider/runtime resolution, enabled toolsets, terminal backend, memory/session policy, MCP configuration, and trajectory/session export references. Persistent memory must either be disabled/reset for benchmark runs or explicitly snapshotted and hashed as part of the run provenance.
- **OpenClaw:** A command-manifest adapter and, if warranted, a native trusted OpenClaw plugin adapter can run at least one LFB fixture and one LAB fixture; conformance records OpenClaw version/commit, provider/model route, harness ID, runtimePlan/tool policy, transcript mirror behavior, selected native runtime, and fail-closed behavior when the requested harness is unavailable. The adapter must respect OpenClaw’s split where core owns provider/model/auth/tool policy and the harness executes a prepared turn.
- **Baselines:** OpenAI Responses/Codex-style and Claude Agent SDK adapters pass conformance as provider/runtime baselines, using API-key auth assumptions and no unsupported subscription-login claims.
- Each first-class adapter has docs, sample manifests, conformance fixtures, a minimal no-network fixture mode where feasible, and at least one public community submission example that publishes only to the community comparison site.
- Adapter results are grouped by suite/scoring mode/selection and never promoted into official LegalForecastBench outputs.

**Key files:**

- New: `examples/adapters/lq-ai/*`, `examples/adapters/hermes-agent/*`, `examples/adapters/openclaw/*` or equivalent `community/adapters/*` paths chosen by implementation
- New/modified docs: `docs/multiharness-adapter-spec.md`, adapter-specific setup pages, and community submission examples
- Existing/new tests: conformance fixture tests and adapter manifest tests for LQ.AI, Hermes Agent, OpenClaw, OpenAI Responses/Codex-style, and Claude Agent SDK examples
- External references: LQ.AI repo/docs, Hermes Agent docs, OpenClaw harness/plugin docs, OpenAI Responses docs, Claude Agent SDK docs

**Dependencies:** Items 1–16.

**Size:** XL.

## Execution Order

1. Item 1 — Canonical multi-harness schemas
2. Item 2 — Task loaders for LegalForecastBench and Harvey LAB
3. Item 3 — Deterministic task selection and partial-run support
4. Item 4 — Host-owned sandbox policy planner
5. Item 5 — Adapter protocol and language-agnostic command adapter
6. Item 6 — Built-in LFB native adapter and projection layer
7. Item 7 — Adapter conformance suite for contributors
8. Item 8 — Multi-harness runner
9. Item 9 — Harvey LAB CLI bridge adapter
10. Item 10 — CLI command group
11. Item 11 — Community submission schema and validation
12. Item 12 — Community aggregation and static comparison site
13. Item 13 — Official and community website generation
14. Item 14 — Community validation workflow
15. Item 15 — Contributor-facing docs and examples
16. Item 16 — Release-check integration, package publication, and no-network smoke tests
17. Item 17 — First-class external harness adapter tracks: LQ.AI, Hermes Agent, and OpenClaw

The order deliberately creates a testable core before the first-class external harness adapters. Implementation agents should commit after each independently passing slice and avoid touching official workflows except where explicitly scoped.

## Risks and Mitigations

- **LAB CLI drift:** LAB is CLI/filesystem-first and may not expose the exact root/output controls this bridge wants. Mitigate by isolating command construction, pinning/recording LAB commit, testing against a fixture command in CI, and failing clearly when real LAB flags do not support the requested mode.
- **Metric confusion:** LFB Brier scores and LAB pass rates measure different things. Mitigate by grouping reports by family/scoring mode/selection and avoiding cross-suite overall rankings.
- **Sandbox overclaiming:** Docker/Podman isolation and provider egress policy are easy to overstate. Mitigate by recording `sandbox.plan.json`, keeping tool containers network-disabled by default, and treating provider API calls as host-process events with declared env vars.
- **Public artifact leaks:** Community submissions may include raw outputs, documents, transcripts, or secrets. Mitigate by defaulting raw outputs to private artifacts, scanning public summaries/sites with `publication_guardrails.py`, and requiring attestations.
- **Unreviewed upload risk:** A fully automatic upload endpoint could publish bad data, secrets, or spam. Mitigate by making GitHub PRs the reviewed registry of record in v1; optional Hugging Face uploads are referenced by immutable URL and hash, then accepted only after validation and merge.
- **Partial-run rollup errors:** Composite rows could accidentally combine incompatible shards. Mitigate with strict compatibility keys, non-overlap checks, visible coverage matrices, and per-shard contributor attribution.
- **Contributor complexity:** Harness adapters can be hard to package. Mitigate with command-manifest adapters, fixture examples, and plain-English conformance reports.
- **Official/community boundary erosion:** Community paths must not reuse official S3/protected workflows. Mitigate with separate schemas, separate workflows, separate site outputs, and workflow tests that reject official environment/OIDC references.
- **Provider/subscription ambiguity:** Users may want to run through subscriptions they already own. Mitigate by supporting user-installed command adapters where allowed, but requiring auth-mode disclosure and not claiming unsupported Claude/OpenAI subscription rights.

## Open Questions

- Final public names and branding for the two sites should be approved by John Hughes / Legal Quants before public launch. Working names in this plan are **LegalForecastBench Official Results** and **LegalForecastBench Community Harness Comparisons**.
- First-class LQ.AI, Hermes Agent, and OpenClaw support is now part of the plan. Implementation still needs to choose exact installation/version pinning for each adapter and decide whether each begins as a command-manifest bridge, in-process adapter, native plugin, or both.
- The plan now recommends GitHub PRs as the canonical metadata/review path and Hugging Face Datasets or GitHub Releases as immutable large-artifact mirrors. Implementation still needs to choose the exact organization/repo names, retention policy, and whether HF upload helpers are included in v1 or documented as a manual step.

## References

- Local adapter seam: `legalforecast/evals/inspect_task.py:40`, `legalforecast/evals/inspect_task.py:118`, `legalforecast/evals/inspect_task.py:126`, `legalforecast/evals/inspect_task.py:402`
- Local packet/prompt/parser/scoring seams: `legalforecast/evals/packet_builder.py:147`, `legalforecast/evals/packet_builder.py:167`, `legalforecast/evals/inspect_task.py:317`, `legalforecast/evals/inspect_task.py:346`, `legalforecast/evals/output_parser.py:208`, `legalforecast/evals/scorers.py:227`
- Official/community separation constraints: `.agents/AGENTS.md:11-16`, `.github/workflows/run-benchmark.yaml:65-70`, `.github/workflows/run-benchmark.yaml:107-112`, `legalforecast/publication/official_aggregate.py:200-274`, `legalforecast/publication/publication_guardrails.py:16-100`
- CLI and testing seams: `legalforecast/cli.py:214-425`, `legalforecast/cli.py:1402-1509`, `tests/test_inspect_task.py:32-105`, `tests/test_inspect_ai_adapter.py:29-94`, `tests/test_harness_sandbox.py:35-104`, `tests/test_official_eval_matrix_workflow.py:9-147`
- Harvey LAB repo and pinned commit: <https://github.com/harveyai/harvey-labs/> and <https://github.com/harveyai/harvey-labs/commit/b4b960e4bd4471553c324d82bf5457bc017cbdf2>
- Harvey LAB architecture, task/harness, sandbox: <https://github.com/harveyai/harvey-labs/blob/b4b960e4bd4471553c324d82bf5457bc017cbdf2/docs/architecture.md>, <https://github.com/harveyai/harvey-labs/blob/b4b960e4bd4471553c324d82bf5457bc017cbdf2/harness/run.py>, <https://github.com/harveyai/harvey-labs/blob/b4b960e4bd4471553c324d82bf5457bc017cbdf2/sandbox/README.md>
- LQ.AI repo/README: <https://github.com/LegalQuants/lq-ai> and <https://raw.githubusercontent.com/LegalQuants/lq-ai/main/README.md>
- Hermes Agent docs and architecture: <https://hermes-agent.nousresearch.com/docs/> and <https://hermes-agent.nousresearch.com/docs/developer-guide/architecture>
- OpenClaw agent harness docs: <https://docs.openclaw.ai/plugins/sdk-agent-harness>
- OpenAI Codex/Responses docs: <https://openai.com/index/unrolling-the-codex-agent-loop/> and <https://developers.openai.com/api/reference/resources/responses/methods/create>
- Claude Agent SDK docs: <https://code.claude.com/docs/en/agent-sdk/overview>
- Hugging Face dataset upload and repository docs: <https://huggingface.co/docs/hub/en/datasets-adding>, <https://huggingface.co/docs/hub/en/repositories-getting-started>, and <https://huggingface.co/docs/hub/main/repositories>
- GitHub deployment and Pages docs: <https://docs.github.com/actions/deployment/about-deployments/deploying-with-github-actions> and <https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site>

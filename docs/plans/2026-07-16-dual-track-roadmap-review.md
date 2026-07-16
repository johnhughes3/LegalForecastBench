# Strategic Review: Dual-Track Launch Roadmap (2026-07-16)

Reviewer: Claude Fable 5, at John's request. Subject: `docs/plans/2026-07-16-dual-track-launch-roadmap.md`, issue #203, the `dm0g` portfolio, and PR #205.

Audience for this document: the planning/architecting model. Treat every item below as feedback to incorporate, not as a replacement plan. Where I say "add" or "re-gate," you own the mechanics of doing that cleanly in the plan and the Beads graph.

## Verdict in three sentences

The plan is exceptionally rigorous and its engineering judgment is mostly right — the modular-monolith call, the exact-100/reserve-150 split, the honest "harness-plus-model" labeling, and the dual-launch independence are all correct and I endorse them. Its strategic flaw is that it optimizes for *defensibility* when the mission requires *results, speed, and audience*: there is no publication/engagement workstream at all, and the first Claude Code result — the thing Jamie Tso asked for and the single most promotable artifact available — is gated behind roughly twenty work packages of contributor-grade security hardening that a trusted local run does not need. Restructure so a preliminary, honestly-labeled paired result exists within days, a communication track exists at all, and the full reproducible pipeline lands behind it — without weakening the two invariants that actually protect credibility (no credentials in artifacts; solver never sees grader material).

## Context the plan under-weights

John's goals for this project, in priority order as I understand them:

1. **Personal traction and marketability** — toward a big-law/boutique AI-practice partner role or a senior lawyer role at an AI research lab. The currency for both audiences is *published results with a credible story*, not infrastructure. A hiring partner will read a leaderboard page and a two-page methods summary; a lab researcher will read a methods writeup and check whether the contamination story holds. Neither will ever see a hash-bound finalizer receipt.
2. **LegalQuants excitement and promotion** — Jamie Tso asked a specific, timely question on 2026-07-16: *"would it make sense for us to test the CC harness against Harvey LAB? has anyone done that already?"* The answer "no one has — here's our paired result" is worth 10x more this month than next quarter. This is a race: now that Claude Code headless is widely available, the CC-vs-thin-harness-on-LAB experiment is obvious, and someone else will run it. Being first, with LegalQuants amplifying, is the whole opportunity.
3. **A genuinely rigorous research contribution** — the existing METHODS.md foundation (micro-Brier, calibration, post-cutoff decision anchor, pre-decision record only, ForecastBench lineage) is already strong and is the differentiator. Rigor should be preserved *in the claims*, which is cheap, rather than *in universal infrastructure before any result exists*, which is what the plan currently does.

The plan serves goal 3 superbly, goal 1 not at all, and goal 2 too slowly.

## Major findings

### 1. There is no audience workstream. Add Track P (publication and engagement).

I grepped the full plan: no work package covers a writeup, announcement, leaderboard presentation quality, README positioning, a methods preprint, or any interaction with LegalQuants beyond defensive non-affiliation language. "Publication" in O-27 means artifact emission, not communication. For a project whose purpose is traction, this is the largest gap — results that aren't communicated might as well not exist.

Add a small Track P (one agent-equivalent, can live in the W3 lane) with roughly these packages:

- **P-P1: Cycle 1 public report and leaderboard page.** The existing `public/report/leaderboard.json` needs a human-facing rendering: a clean static page with the headline table (micro-Brier, calibration, refusal rates), the one-paragraph contamination story, and links to METHODS.md and the reproduce-or-audit path. This is the artifact John links in every conversation with a firm or a lab. Design it for a skimming reader; the audit trail is one click deeper, not on the front page.
- **P-P2: Harness-comparison writeup.** A short, honest post for the first paired CC-vs-native-LAB result: what was run, what was matched, what wasn't, score + cost + wall-clock per arm, and explicit "n is tiny, this is plumbing-plus-preliminary-signal" framing. Written *with* the preliminary run (see finding 2), updated at pilot completion.
- **P-P3: LegalQuants engagement loop.** Reply to Jamie on the thread that spawned #196 with the plan and, days later, the preliminary result. Invite LegalQuants input on the stratified pilot shard selection (E-08) — co-designing the pilot converts them from audience into promoters, at zero rigor cost since shard selection is pre-registered before scores are seen anyway. The plan currently treats LegalQuants purely as a trademark risk; they are the distribution channel.
- **P-P4: Methods preprint (SSRN, optionally arXiv cs.CL).** After Cycle 1 publishes, a 6–10 page paper: design, contamination resistance, Cycle 1 results, harness-comparison appendix. For the AI-lab audience this single artifact outweighs everything else in the repo; for the legal audience SSRN is native ground. METHODS.md is already 70% of the content.
- **P-P5: README as a landing page.** The README will be read by two audiences with opposite needs (potential contributors; people evaluating John). Make the first screen say what the benchmark is, show the current leaderboard snapshot, and state the contamination claim — before any contributor mechanics.

None of this blocks or is blocked by engineering waves. It should start now, not at Wave 6.

### 2. The critical path to the first Claude Code result is far too long. Add a Tier-0 preliminary run.

E-04 (the Claude Code one-task smoke) depends on **R-01 through R-10, H-01 through H-06, A-04, A-11, and E-03** — hardened container runtime, receipt/resume binding, process-group cancellation, hostile runtime canaries, redaction centralization, capability probes, fake executables, auth-profile binding, and a five-package LAB bridge — plus Wave 4's hostile E2E before any live smoke in Wave 5. That is weeks of wall-clock before the artifact Jamie asked about exists in any form.

The security threat model doesn't support this gating. R-06 through R-10, Q-06, Q-07, and the #41 network-disabled container boundary defend against **untrusted contributors and hostile submissions**. The first run is *John, on his own machine, on Harvey LAB's public open-source tasks, with his own credentials*. There is no confidential matter data, no hostile input, and no third party. Only two invariants genuinely protect credibility at Tier 0:

1. No provider credential, token path, or account identifier appears in any published artifact.
2. The solver never sees evaluator-private material (rubrics, grader prompts, answer keys).

Both are enforceable with a scoped workspace, a curated task-materialization step, and a redaction pass over outputs — days of work, not weeks.

Implementation clarification accepted after review: pinned public task bytes are still treated as untrusted input. Before either Tier-0 solver starts, the native process runs in a disposable sandbox with an isolated HOME/XDG/session state, provider credentials injected through the narrow supported mechanism, filesystem access scoped to curated read-only solver input plus a narrow writable output root, no ordinary home or repository mount, and evaluator-private material physically absent. Output allowlisting and redaction remain publication gates, not substitutes for pre-execution isolation.

**Concrete restructuring ask:** add **E-00: Tier-0 operator-run preliminary paired smoke**, with dependencies only on E-01 (provider-terms check), H-01 (pin the LAB commit), a *lite* version of task materialization and output discovery, and a basic redaction check. Run the pinned smoke task (`identify-issues-in-counterparty-motion-brief`) through (a) local Claude Code headless and (b) the native LAB thin harness with the same pinned model via API, score both with the pinned LAB evaluator, and publish with an explicit **"preliminary — not yet independently reproducible"** label. Re-gate R-06–R-10, Q-06, Q-07, and the full #41 boundary onto the **contributor-intake gate (Outcome C2 / Gate C-D1)** where they belong. RISK-04's mitigation (labeling) already concedes that preliminary local results are legitimate when labeled; the plan just never schedules one.

This also requires amending #196's acceptance criteria — split it into "preliminary paired smoke" and "reproducible community adapter." The issue text is a tool John controls, not a constraint; the plan currently treats it as near-immutable (E-04's acceptance defers to "a reviewed issue amendment"). Do the amendment as part of landing this review.

Sequencing result: Tier 0 produces the promotable result and de-risks every downstream assumption (headless flags, evaluator invocation, output discovery, model pinning) *before* the pipeline is built around them. The full reproducible path then confirms and supersedes the preliminary number. That's the correct order for both speed and engineering risk — right now the plan builds the factory before tasting the recipe.

### 3. Tool-mediation may destroy the very thing being measured. Decide containment strategy now, top-down.

Jamie's question is whether Claude Code's *rich harness* — its native Read/Write/Bash/Grep/agentic loop — outperforms LAB's thin loop. The plan's architecture (per #196 and R-00A/A-04) strips Claude Code's built-in tools and routes everything through a strict MCP shim into the #41 container. That measures "Claude Code's planner with a foreign minimal toolset," which is a materially different — and much less interesting — arm. R-00A honestly acknowledges this risk ("records whether the profile remains representative enough to call `Claude Code`") but treats it as an empirical finding to discover later, *after* A-01–A-04 are built around tool-mediation.

Flip the default: **contain around the harness, don't amputate it.** Run the Claude Code process itself inside an isolated, throwaway workspace (container or hard-scoped sandbox) with its *native* tools enabled inside that boundary, network egress limited to the provider API, isolated HOME/XDG, no session persistence, and credentials injected without landing in artifacts. That preserves the characteristic harness — which is the scientific object of study — while holding the two Tier-0 invariants. The MCP-mediated profile remains valuable as a *second* arm (it isolates "planner effect" from "toolset effect"), but it should not be the definition of "the Claude Code harness." Make this an explicit design decision in §8 now, before A-04 hard-codes the wrong default. Same logic applies to Codex (R-00B): Codex's own sandbox modes are the harness; use the narrowest native mode, not a replacement.

### 4. Time-to-dispatch for the official run is a validity property, not a convenience. Date-box the waves.

The June 30, 2026 decision anchor is the contamination claim: models with earlier knowledge cutoffs cannot have seen the outcomes. That claim decays. Every week of delay (a) shrinks the set of frontier models for which the anchor is comfortably post-cutoff, (b) increases the risk that a model released mid-plan forces registry rework, and (c) increases pressure to re-freeze. The plan's waves have no dates at all.

Add target dates to §21 (aggressive but honest — e.g., Tier-0 smoke within ~1 week, official freeze/dispatch within ~4–6 weeks of the plan date, adjusted by the acquisition agent's actual throughput), and add a risk-register entry: **anchor decay / model-registry staleness**, with the mitigation being schedule discipline and a pre-committed registry cut date. "ASAP" is in John's stated goals twice; the plan should quantify it.

### 5. Plan mass threatens the schedule it plans. Mark the critical path and cap WIP.

122 work packages, 105 new Beads, 767 live tracker records, 11 gates, 20 risks, and a checkpoint ceremony (PR URL + merge SHA + green checks + independent review + refresh + post-refresh characterization tests) — executed by ~9 agents. The meta-risk the register omits: **the process consumes the schedule**. Agents in a rich ready-queue drift to satisfying, non-critical work (Q-05 drift probes, mutation emphasis, I-lane archaeology) while E-00/E-04 and the corpus gates starve.

Asks:

- Annotate the two critical paths explicitly in the Beads graph (a `critical-path` label or priority convention): roughly O-00→O-05/O-06→O-13→…→O-26 for the official track, and E-01→H-01→E-00→(A-wave)→E-04/E-05→E-07 for the community track. Instruct every agent: never pull off-critical-path work while critical-path work is ready in your lane.
- Explicitly park the long tail. Q-05, Q-08–Q-09, I-04, I-07, I-08, I-09, E-12, and the mutation-testing emphasis are post-launch; say so in the graph, not just in wave prose.
- Lighten the checkpoint ceremony for docs-only and test-only PRs (skip post-refresh characterization tests there).
- Schedule a post-launch tracker pruning pass; 767 records is already at the scale where the tracker misleads more than it guides.

### 6. Elevate cost and wall-clock to headline metrics of the harness comparison.

E-04's deliverables include a cost report, but the comparison semantics (§7.9) rank on score. For every audience that matters here — law firms deciding what to deploy, LegalQuants' practical bent, labs studying harness efficiency — **$/task, tokens, and minutes per arm are as interesting as the rubric delta**. "Claude Code scored +N points but cost 6x and took 4x longer" is a finding; it's arguably *the* finding for practitioners. Make score, cost, tokens, and wall-clock co-equal columns in the score artifact and the comparison output, and report variance across repeats (E-08's repeat policy already gives you the data). This is nearly free and doubles the writeup's substance.

Implementation clarification accepted after review: subscription execution is never reported as `$0` and is not assigned a comparable `$/task` unless a frozen accounting basis supports it. The amended roadmap records raw tokens and wall-clock separately, labels direct provider charges versus list-price-equivalent estimates, and uses `subscription_unallocable` when marginal or amortized subscription cost cannot be allocated without false precision.

## Endorsements (do not relitigate these)

- **Modular monolith, no monorepo before launch.** Correct. The split trigger in §5.4 is the right shape. Repackaging now would burn weeks against zero user-visible value.
- **Exact-100 launch with ≥150 reserve, hash-bound output-blind projection.** Correct, and the pre-registration-without-the-bureaucracy flavor (freeze before model exposure) is exactly the right rigor/weight tradeoff given the project explicitly declined formal preregistration.
- **"Harness-plus-model configuration" labeling for subscription runs.** This honesty is a feature; keep it verbatim in public copy.
- **No mutual blocking edge between official and community tracks; launches don't wait for each other.** Correct and important.
- **Worktree topology (4 slots, ~8 agents + coordinator, W3-parks-to-Codex trick).** Sound. Single-writer rule on the live acquisition store is non-negotiable and correctly stated. One adjustment only: W2/C1's first deliverable becomes E-00 (Tier-0 smoke) rather than fakes/probes.
- **Never blocking on #47 (LQ.AI bridge) until LegalQuants supplies a contract.** Correct — engage them socially (P-P3), not architecturally.

## Smaller notes

- **Baselines in the Cycle 1 report.** `evals/baselines.py` and `human_baseline.py` exist; make sure the published Cycle 1 report *surfaces* a naive base-rate reference (and any human reference data available) next to model Brier scores. LegalQuants are quants — an uninterpretable absolute Brier number without a base-rate anchor is the first thing they'll poke at. If it's already wired into O-27's report, state it in the work package's acceptance criteria so it can't silently drop out.
- **Provider-terms check (E-01):** also verify each provider's stance on *publishing* benchmark results from subscription-tier usage, not just automation legality. Record once, cite in the writeup.
- **Naming:** "Community Harness Comparisons" is accurate and safely unbrandable — fine for the repo feature. When P-P2 publishes, consider a memorable program name (decide then, not now; don't spend cycles on it).
- **Risk register additions:** (a) scooped — someone else publishes CC-vs-LAB first (mitigation: Tier 0); (b) anchor decay (finding 4); (c) process-consumes-schedule (finding 5).
- **The four planning reviews already run were all rigor-oriented** (architecture, security/premortem, issue coverage, Beads conversion). None asked "who is the audience and when do they see something?" Add that lens to Q-10's fresh-eyes review charter.

## Priority order for incorporating this review

1. **E-00 Tier-0 paired smoke** + #196 amendment + containment-strategy decision (findings 2 and 3). This is the wall-clock unlock; everything else in the community track re-sequences behind it.
2. **Track P work packages** (finding 1), started immediately in parallel — P-P3 (reply to Jamie) costs an hour.
3. **Critical-path annotation and long-tail parking** in the Beads graph (finding 5).
4. **Date-boxed waves + risk additions** (finding 4).
5. **Metric elevation in the score/comparison contracts** (finding 6) — cheap now, expensive after the contracts freeze in F-05/F-08.

Everything not listed above stands as planned. The engineering skeleton is strong; give it a public face and a faster first heartbeat.

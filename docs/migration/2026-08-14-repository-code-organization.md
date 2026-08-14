# Repository-wide module decomposition and code organization plan

**Date:** 2026-08-14

**Status:** proposed; implementation requires approval and the dependency gates recorded in Beads

**Reference commit:** `5a8440a2`

**Planning bead:** `legalforecastbench-6ppo`

**Existing programs retained:** `LegalForecastBench-cwdv`, `LegalForecastBench-l8qv.15`

**Cycle 1 change-control gate:** `LegalForecastBench-5qd6.41`

This document is the repository-wide umbrella. The earlier [CLI and package reorganization plan](2026-08-12-cli-and-package-reorganization.md) remains the detailed CLI execution appendix, and [CLI seam analysis](2026-08-12-cli-seam-analysis.md) remains historical empirical support. Where this umbrella changes sequencing, thresholds, or repository-wide ownership, this document controls; CLI-specific compatibility details remain additive rather than a second competing program.

## Outcome

Replace the repository's handful of true monoliths and its long tail of oversized, mixed-responsibility modules with cohesive packages, small stable facades, explicit dependency directions, and tests organized around domain contracts rather than the physical location of implementation details.

This is a behavior-preserving organization program, not a rewrite. The public `legalforecast` executable, `legalforecast.cli:main`, command syntax, exit behavior, supported imports, exact artifact bytes, authenticated source identities, schemas, authority boundaries, resume semantics, and provider-spend controls remain stable unless a separately approved versioned migration explicitly says otherwise.

The plan covers every tracked Python source, test, script, and example adapter through a generated architecture inventory. It does not mechanically split every file above an arbitrary line count. Files in the 500–999-line watch tier are owned and reviewed at the package-lane level; files at least 1,000 lines, symbols above 400 lines, forbidden-cycle or reverse-edge participants, authenticated-path participants, and similarly high-risk files require an explicit extraction/move disposition or a reviewed cohesion exemption.

## Audit snapshot

At the reference commit the repository contains 612,269 lines across tracked Python files.

| Surface | Python files | At least 500 lines | At least 1,000 lines | At least 1,500 lines | At least 2,000 lines |
| --- | ---: | ---: | ---: | ---: | ---: |
| `legalforecast/` | 331 | 180 | 87 | 41 | 20 |
| `tests/` | 409 | 165 | 80 | 48 | 31 |
| `scripts/` | 14 | 6 | 2 | 1 | 1 |
| `examples/` | 4 | 0 | 0 | 0 | 0 |
| Total | 758 | 351 | 169 | 90 | 52 |

The 500-line number is a review signal from the repository conventions, not a pass/fail target. The program uses three levels:

- **Watch:** 500–999 lines. Inventory automatically and assign to a package lane; check for mixed ownership, growing public surface, large symbols, high churn, or dependency cycles without requiring an individual bead or exemption merely because of size.
- **Oversized:** 1,000–1,999 lines or any top-level symbol above 400 lines. Require a recorded disposition: planned seam or reviewed cohesion exemption.
- **Monolith:** at least 2,000 lines, a class/function above 800 lines, or a file combining three or more architectural layers. Require a concrete decomposition plan except for generated or immutable historical material, which must be explicitly classified rather than silently ignored.

The current CLI architecture ratchet is useful but intentionally narrow. It records `legalforecast/cli.py`, reverse CLI dependencies, and test compatibility coupling. It does not yet inventory all oversized modules or enforce package-layer direction repository-wide.

## Primary findings

### 1. `legalforecast/cli.py` remains the dominant monolith

`legalforecast/cli.py` is 72,456 lines with 992 top-level definitions, 19 top-level classes, 165 command handlers totaling 26,960 lines, 160 verifier-family functions totaling 11,941 lines, and a 1,773-line `build_parser()`.

It was touched by 274 commits in the trailing three-month window, far more than any other file, so its size is not merely aesthetic: it is the repository's dominant merge-conflict and coordination surface.

The checked-in architecture inventory records 108 test/support files importing the CLI, 58 files consuming private CLI members, 704 monkeypatch occurrences, and eight production reverse dependencies. Some recently extracted modules still probe the CLI at runtime to preserve legacy monkeypatch behavior, so moving text without changing dependency ownership would recreate the same monolith across files.

The existing `LegalForecastBench-cwdv` program remains the authority for this work. This plan does not create a competing CLI epic; it makes its children granular and connects the CLI program to the rest of the repository-wide organization graph.

### 2. `legalforecast.ingestion` is both too flat and internally too large

`legalforecast.ingestion` contains 154 Python modules and 153,534 lines in one mostly flat package. Of those modules, 107 exceed 500 lines and 60 exceed 1,000 lines. Its 613-line `__init__.py` eagerly aggregates a broad compatibility surface, and package-level imports amplify cycles and make narrow imports harder to discover.

The existing ingestion module map provides a good ownership vocabulary and correctly records that the flat layout is intentional while active acquisition work continues. That rationale expires only after the Cycle 1 gate and the required dependency/identity inversions. The target should use the map as migration input, remeasure the live import graph, and move cohesive vertical slices only after CLI reverse dependencies and authenticated implementation identities have been handled.

### 3. The worst non-CLI modules expose real seams

The following production monoliths have both high size and clear internal boundaries. The target modules below are ownership destinations, not permission to perform bulk moves in one pull request.

| Current file | Lines | Main problem | Proposed seams |
| --- | ---: | --- | --- |
| `legalforecast/ingestion/case_dev_purchase.py` | 6,415 | Policy, client, durable schema, journal mutation, reconciliation, snapshots, and migration live together; `CaseDevPurchaseJournal` spans 2,309 lines. | `purchase/models`, `purchase/policy`, `purchase/client`, `purchase/store`, `purchase/reconciliation`, with a compatibility facade exporting the current public names. |
| `legalforecast/labeling/llm_pipeline.py` | 5,535 | Unitization, structural review, labeling, prompts, provider shard execution, merge, and review application share one module. | `labeling/prompts`, `labeling/unitization_stage`, `labeling/structural_review_stage`, `labeling/outcome_stage`, `labeling/shards`, and `labeling/review_application`. |
| `legalforecast/ingestion/cycle_acquisition_store.py` | 3,919 | One 2,681-line store class owns schema, search pages, observations, Firecrawl attempts, raw artifacts, snapshots, and reconciliation. | `cycle/store/schema`, `cycle/store/search`, `cycle/store/observations`, `cycle/store/firecrawl`, `cycle/store/artifacts`, and `cycle/store/snapshots`, behind a stable store facade/transaction boundary. |
| `legalforecast/ingestion/recap_api_batch_driver.py` | 3,562 | Discovery seeding, observation execution, saturation analysis, ranking, tranche materialization, and CLI-facing orchestration are mixed. | `providers/recap/batch/seed`, `observe`, `saturation`, `priority`, and thin orchestration. |
| `legalforecast/ingestion/resolved_post_recovery.py` | 3,428 | Validation, issue collection, document building, authenticated clearance, capability use, and publication are intertwined. | `recovery/resolved/models`, `validation`, `issues`, `builder`, `lineage`, `authority`, and `publication`. |
| `legalforecast/ingestion/target_public_gap_refresh.py` | 3,215 | Planning, execution, verification, source authentication, and output publication share one module. | `screening/target_gaps/plan`, `execute`, `verify`, `sources`, and `publish`. |
| `legalforecast/ingestion/replacement_purchase_approval.py` | 2,959 | Multiple approval versions, request construction, authority verification, transition replay, and ranked-reserve variants are coupled. | `purchase/approval/models`, `build`, `verify`, `transition_replay`, and version-specific adapters. |
| `legalforecast/ingestion/courtlistener_case_dev_bridge.py` | 2,833 | Provider records, validation, document matching, gap reconciliation, and batch orchestration share one file. | `providers/bridges/models`, `validation`, `documents`, `paid_gaps`, and `batch`. |
| `legalforecast/ingestion/stage_a_lineage_verification.py` | 2,763 | Parse, unitization, provider replay, review, and packet-authority verification are grouped by historical CLI extraction rather than domain. | `unitization/lineage/parse`, `unitization`, `provider_replay`, `review`, and `packet_authority`. |
| `legalforecast/publication/official_aggregate.py` | 2,687 | Input verification, score aggregation, baselines, repeat variance, run-card construction, output publication, and parser code are mixed. | `publication/aggregate/inputs`, `scores`, `baselines`, `variance`, `run_card`, `outputs`; parser registration moves to console adapters. |
| `legalforecast/ingestion/cycle_orchestrator.py` | 2,459 | Stage metadata, state transition, external adoption, filesystem safety, and verifier routing are maintained together. | `cycle/registry`, `cycle/state_machine`, `cycle/adoption`, `cycle/filesystem`, and `cycle/runner`. |
| `legalforecast/ingestion/docket_decision_text_source.py` | 2,205 | Source models, replay, screening capture, terminal disposition validation, and artifact verification are mixed. | `documents/decision_text/models`, `source`, `replay`, `screening`, and `verify`. |
| `legalforecast/evals/per_case_runner.py` | 2,176 | Configuration, resume validation, solver selection, execution, accounting, and publication share one runner. | `evals/per_case/config`, `resume`, `solver`, `execute`, `accounting`, and `publish`. |
| `legalforecast/ingestion/provenance_clearance.py` | 2,166 | Three schema generations, planning, authentication, review worksheet handling, capability issuance, and finalization are combined. | `disclosure/provenance/models`, `plan`, `authenticate`, `review`, `capability`, and `finalize`, retaining versioned codecs. |
| `legalforecast/labeling/provider_cycle_caps_materializer.py` | 2,131 | Policy loading, preflight, materialization, staged commits, and run-card completion are combined. | `labeling/caps/policy`, `preflight`, `materialize`, `commit`, and `run_card`. |
| `legalforecast/unitization/review.py` | 2,130 | Models, validation, application, terminal review, and finalization live together. | `unitization/review/models`, `validate`, `apply`, `terminal`, and `finalize`. |
| `legalforecast/ingestion/target_raw_docket_recovery.py` | 2,120 | Plan variants, execution, retry policy, artifact publication, and receipt verification are mixed. | `recovery/raw_docket/plan`, `execute`, `retry`, `artifacts`, and `receipt`. |
| `legalforecast/ingestion/ranked_reserve_replacement.py` | 2,096 | A 789-line planner sits beside output binding, legacy validation, replay, and capability checks. | `recovery/reserve/plan`, `selection`, `bind`, `legacy`, and `replay`. |
| `legalforecast/ingestion/recap_api_discovery.py` | 2,088 | Provider models, pagination, docket reconstruction, candidate observation, and source-binding verification share one module. | `providers/courtlistener/recap/models`, `pagination`, `reconstruct`, `observe`, and `source_binding`. |

The 21 additional production files between 1,500 and 1,999 lines join the same owner lanes rather than becoming a separate cleanup wave: snapshot replay, free document download, screening union, acquisition screening, packet planning, repair execution, policy rebind, screening identity, decision-text artifacts, CourtListener snapshot/client/fetch/acquisition, missing-document successor, purchase approval, candidate-scoped Stage A replay, terminal purchase failure, multiharness community packaging, provider journaling, and shard fan-in.

All 46 production files between 1,000 and 1,499 lines must be present in the architecture inventory and are reviewed within their package lane. A lane may retain a cohesive module, but must record why its public surface and largest symbol are reasonable and how growth is fenced.

### 4. Stateful classes and giant functions are stronger warning signals than file size alone

The largest symbols cross transaction and authority boundaries: `CycleAcquisitionStore` is 2,681 lines, `CaseDevPurchaseJournal` is 2,309, `ProviderAttemptJournal` is 1,070, and both DynamoDB and SQLite spend-authority classes exceed 600 lines. These should be decomposed around explicit repositories/services while preserving transaction ownership and a single public facade; splitting individual methods into free functions without moving state ownership would make the design worse.

The largest functions likewise reveal workflow boundaries: `verify_materialized_downstream_lineage` is 979 lines, `plan_ranked_reserve_replacements` is 789, `collect_resolved_post_recovery_build_issues` is 666, and several Stage A verifiers exceed 400 lines. Characterize their inputs, outputs, side effects, final rechecks, and failure ordering before extracting pure phases.

### 5. Other top-level packages need their own organization lanes

`legalforecast.multiharness` now has 53 modules and 32,745 lines; 28 modules exceed 500 lines and 12 exceed 1,000. Its natural boundaries are contracts/identity, adapters, contained runtimes, materialization, execution/runner, receipts/deliverables, evaluation/scoring, and community publication. Those boundaries should become subpackages before the directory grows further.

The labeling, publication, evaluation, unitization, and protocol packages contain fewer files but several critical monoliths. These should be split along existing contract boundaries rather than absorbed into ingestion or a generic `utils` package.

### 6. Test size mirrors production coupling

Eighty test modules exceed 1,000 lines and 31 exceed 2,000. The largest files mix domain-unit tests, CLI adapter tests, end-to-end scenarios, fixtures/builders, replay/tamper matrices, and compatibility tests.

Examples include `tests/test_acquisition_cli.py` at 5,747 lines, `tests/test_cycle_orchestrator_cli.py` at 4,665, `tests/test_target_100_acquisition.py` at 4,491, `tests/test_resolved_post_recovery.py` at 4,421, and `tests/test_llm_labeling_cli.py` at 3,958. Some individual test functions exceed 1,000 lines because setup, execution, and assertions are handwritten in one body.

Tests must be reorganized in lockstep with production seams. Mechanical splitting by line range would duplicate fixtures and obscure behavioral coverage. The target separates domain tests, adapter/CLI contract tests, persistence/replay tests, tamper/failure-order tests, and explicit end-to-end scenarios, supported by narrow domain fixture builders rather than one global test utility monolith.

### 7. Two probe scripts are application-sized programs

`scripts/probe_claude_code_native_containment.py` is 2,187 lines and `scripts/probe_codex_native_containment.py` is 1,185. The Claude probe combines protocol parsing, state accumulation, process canaries, sandbox/boundary validation, evidence projection, and outer/inner orchestration. Shared protocol and evidence code belongs in importable, tested modules; provider-specific launch and characterization remain separate adapters.

The four scripts between 500 and 999 lines (`release_check.py`, `verify_review_blockers.py`, `official_infra_contract.py`, and `probe_codex_cli_interface.py`) enter the inventory and receive either a seam or a cohesion exemption. Script entry points remain thin and importable logic remains testable.

## Target dependency architecture

The intended dependency direction is:

```text
public facades and script entry points
                |
                v
console / operational adapters
                |
                v
application services and workflows
                |
                v
domain policies, value types, and ports
                ^
                |
storage and provider adapters implement ports
```

Versioned codecs, commitment primitives, and narrow shared contracts remain stable low-level dependencies. Composition roots may import concrete adapters to construct applications; application and domain code depend on typed ports rather than SQLite, DynamoDB, filesystem, or provider implementations. This requires no dependency-injection framework. Domain modules may not import CLI/console adapters, script modules, or test helpers, and provider transports may not grant authority merely by being selected from metadata.

## Target package layout

The exact destination manifest is produced from the live graph before file moves, but the intended ownership shape is:

```text
legalforecast/
├── cli.py                         # stable facade only
├── console/
│   ├── app.py                     # parse, invoke, error boundary
│   ├── parser.py                  # explicit registrar composition
│   └── commands/                  # thin Namespace-to-typed-call adapters
├── ingestion/
│   ├── contracts/                 # ingestion-local stable vocabulary
│   ├── providers/
│   │   ├── case_dev/
│   │   ├── courtlistener/
│   │   │   └── recap/
│   │   └── firecrawl/
│   ├── cycle/
│   │   └── store/
│   ├── screening/
│   ├── cohort/
│   ├── documents/
│   ├── purchase/
│   ├── recovery/
│   └── disclosure/
├── labeling/
│   ├── stages/
│   ├── prompts/
│   ├── providers/
│   └── caps/
├── unitization/
│   ├── review.py                  # compatibility facade
│   ├── reviews/                   # internal review implementation
│   └── lineage/
├── evals/
│   ├── per_case/
│   └── spend/
├── publication/
│   ├── aggregate/
│   └── fan_in/
├── multiharness/
│   ├── contracts/
│   ├── adapters/
│   ├── runtimes/
│   ├── materialization/
│   ├── execution/
│   └── publication/
└── testing/                       # architecture tooling, not domain fixtures
```

Coherent current packages omitted from the sketch—`config`, top-level `contracts`, `document_need`, `extraction`, `protocol`, `reporting`, and `selection`—remain intact unless their own inventory lane proves a concrete seam. This is a partial destination sketch, not a replacement taxonomy. It is a modular monolith and does not introduce services, new deployment boundaries, separate databases, plugin frameworks, or dynamic dependency injection containers.

## Structural rules

1. Keep public facades stable and small; do not preserve every private historical name indefinitely.
2. Move behavior to the package that owns its vocabulary, not to generic `commands.py`, `helpers.py`, `common.py`, or `utils.py` dumping grounds.
3. Split stateful classes by repository/service responsibility while keeping one transaction owner and preserving lock, idempotency, and write-order semantics.
4. Split validation pipelines into typed phases only after characterization pins failure ordering, final-byte checks, namespace checks, and TOCTOU rechecks.
5. Avoid a bulk directory move. One slice moves implementation, direct callers, tests, docs, architecture inventory, and compatibility shims together.
6. A forwarding module is temporary and must name its removal bead. It must not re-create eager imports or support undocumented monkeypatch-through-old-owner semantics.
7. `legalforecast.ingestion.__init__` and other package facades export deliberate stable surfaces only; internal callers import narrow owner modules.
8. No new file should normally exceed 500 lines. A file above 1,000 lines or a top-level symbol above 400 lines requires a reviewed exemption or immediate follow-up bead.
9. Directory size is also measured: above roughly 20 implementation files, identify and document a subpackage seam rather than continuing flat growth.
10. Never combine a filesystem move, semantic feature change, schema change, and large function split in one pull request.

## Compatibility and security boundaries

The following remain unchanged throughout ordinary slices:

- All three installed entry points: `legalforecast`, `legalforecast-acquisition-systemd-run`, and `legalforecast-provider-env-run`; `legalforecast.cli:main`; command paths, aliases, options, defaults, help meaning, exit codes, stdout, and stderr.
- Exact authenticated artifact bytes, schema identifiers, canonical codecs, digest forms, output paths, ordering, resume/idempotency behavior, and the absence of extra files.
- Network, human-review, provider, purchase, freeze, dispatch, publication, and deploy authority boundaries.
- Provider-spend reservation, settlement, and breaker semantics.
- Historical authenticated implementation-source mappings and their verification.

Because the current Firecrawl screening profiles include `legalforecast/cli.py`, ordinary CLI decomposition is blocked on the post-Cycle-1 versioned source-profile migration tracked by GitHub issue #672 and bead `legalforecastbench-1t2`. Newly emitted commitments may use the narrower versioned profile only after complete chain validation; historical mappings remain accepted.

That migration is necessary but not sufficient for later physical moves. The Firecrawl screening profiles name 21 current paths; sibling resolution uses `Path(__file__).with_name(...)`; REST policy rebind validates historical paths; screening-union compatibility is path-keyed; and multiharness adapters commit implementation and CLI-adapter paths. Every physical-move bead must prove the source is not path/authentication sensitive, perform an explicit versioned transition while retaining historical verification, or record a no-move disposition.

The current no-move/path-sensitive set includes `ingestion/canonical_json.py`, `ingestion/provenance.py`, `ingestion/http_config.py`, `protocol/manifest.py`, `ingestion/cycle_preflight.py`, `ingestion/cycle_preflight_manifest.py`, `ingestion/cycle_lineage_index.py`, and the installed operational entry point `ingestion/infisical_systemd_launcher.py`. Moving one requires its own separately approved and characterized compatibility migration.

Cycle 1 change control forbids using reorganization as a back door to modify frozen codecs, schemas, validators, or publication semantics. Any correctness/security need to change a frozen contract follows the explicit versioned emergency path in `docs/cycle-1-change-control.md` and is not authorized by this plan.

## Architecture inventory and ratchets

The first implementation wave preserves `legalforecast/testing/architecture.py` as a composition facade and moves scanner concerns into a small `legalforecast/testing/architecture_rules/` package such as `inventory.py`, `symbols.py`, `imports.py`, `cli_compatibility.py`, `baseline.py`, and `reporting.py`. The current 822-line architecture module must not become the next tooling monolith. The reviewed data remains separate from the authenticated-contract ratchet.

The inventory records every tracked Python file at or above 500 lines with:

- path, line/nonblank count, top-level definition count, largest symbol and span;
- owner package and architectural layer;
- internal fan-in/fan-out, cycle membership, and recent churn;
- public/documented/dynamic import and qualified-name compatibility obligations;
- authenticated source-identity participation;
- lane owner for every watch-tier file, plus an explicit migration bead or reviewed cohesion exemption for files/symbols/risk cases that cross the manual-disposition threshold;
- target owner/path, compatibility policy, and validation family;
- exemption owner, reason, expiry/review trigger, and maximum permitted growth where applicable.

The pytest-authoritative gate rejects:

- a new file above 500 lines that is absent from the generated inventory or has no package-lane owner;
- a new file at least 1,000 lines, symbol above 400 lines, forbidden edge/cycle, authenticated-path participant, or materially high-churn exception without a manual disposition;
- growth beyond a reviewed ceiling;
- a new top-level symbol above 400 lines without disposition;
- a new reverse dependency on CLI/console/scripts/tests;
- a stale entry after a file shrinks or moves;
- a directory crossing its reviewed flat-file ceiling without a subpackage decision.

The gate does not require shrinking every cohesive file to 499 lines, does not require 351 individual exception records, and does not reward no-op splitting. A review command prints a ranked queue by size, symbol span, churn, cycle membership, authenticated-path participation, and dependency degree so later work selects the highest-value seams.

## Execution program

### Wave 0: establish current truth and safe migration mechanics

1. Extend the architecture inventory from CLI-only to repository-wide oversized-file and package-boundary coverage.
2. Capture supported imports, dynamic imports, module/callable identity checks, authenticated source profiles, and import cycles before moving files.
3. Capture parser/CLI differential fixtures and selected exact-byte artifact corpora for the first planned slices.
4. Capture pytest-xdist module timings and the current critical path; test decomposition must improve diagnosability without regressing suite time.
5. Repair the existing Beads graph so the held source-profile work is truly blocked, overlapping `cli.py` work is serialized, ingestion may begin at its intended point, and the thin-facade capstone waits for test decoupling.

Wave 0 inventory, characterization, and read-only timing work may proceed before the Cycle 1 final gate. Every implementation extraction, physical move, transaction-owner split, or compatibility migration has a direct `LegalForecastBench-5qd6.41` blocker unless an individually reviewed Cycle 1 exception explicitly authorizes that one slice; parent-child links do not inherit blockers.

### Wave 1: finish the existing CLI program

1. Complete the versioned screening implementation-source migration after Cycle 1.
2. Remove all eight production reverse dependencies on `legalforecast.cli`, `legalforecast.console`, and transitional `legalforecast.cli_commands` adapters by moving default collaborators to their domain owners.
3. Split verifier/replay extraction into cohesive families and land them sequentially because each edits the facade.
4. Move command bodies and parser registration in stage-sized slices, leaving typed domain calls and thin adapters.
5. Introduce the narrowly scoped typed stage registry only where CLI and cycle orchestration genuinely duplicate metadata.
6. Retarget domain tests and monkeypatches to owner APIs while retaining a small explicit CLI-contract suite.
7. Reduce `cli.py` to a small facade measured in tens or low hundreds of lines and ratchet it there.

### Wave 2: split stateful persistence and authority cores

This wave precedes broad physical package moves because it creates the interfaces those moves need.

1. Characterize and split `CaseDevPurchaseJournal` into schema/storage, policy, reconciliation, snapshots, and client services while retaining one transaction owner.
2. Characterize and split `CycleAcquisitionStore` into focused repositories behind a stable transaction/store facade. This structural split and the semantic concurrency redesign in `LegalForecastBench-l8qv.11` must be ordered explicitly rather than running as overlapping lanes.
3. Split `ProviderAttemptJournal` within the labeling lane without conflating its durable provider-call identity with spend-control authority.
4. Retain the existing `ProviderSpendAuthority` protocol for SQLite and DynamoDB implementations, then split spend models/contracts from backend adapters while preserving backend-specific durability and conditional-write semantics.
5. Add failure-injection tests for lock acquisition, crash points, torn writes, replay, double settlement, and final rechecks before changing ownership.

### Wave 3: reorganize ingestion in vertical slices

1. Check in the live module-to-destination manifest and supported-import matrix.
2. Record the current 16-module purchase/recovery/authority strongly connected component and `disclosure_clearance`/`disclosure_review_bundle` cycle, then break them through typed ports before physical moves.
3. Shrink `ingestion.__init__` after internal callers use owner modules; preserve deliberate exports with compatibility tests.
4. Move Case.dev provider/client/enrichment/scheduling modules.
5. Move CourtListener and RECAP transport, discovery, fetch, reconstruction, bridge, and batch modules.
6. Move Firecrawl transport, budgets, screening identity, observation, and recovery modules.
7. Move cycle configuration, store, orchestration, assembly, lineage, and readiness modules, retaining current no-move preflight/lineage paths until separately versioned.
8. Move screening, snapshot union/replay, cohort policy/projection, ranking, and selection modules.
9. Move document planning, download, materialization, parse, repair, and decision-text modules.
10. Move purchase approval, recovery, replacement, terminal failure, and reserve workflows.
11. Move disclosure, provenance, clearance, and model-review authority modules last, after cycles have been inverted through explicit interfaces.

Each slice also addresses all oversized files in that owner lane or records a cohesion exemption; moving a 2,000-line file unchanged into a subdirectory does not satisfy the slice.

### Wave 4: decompose labeling, unitization, evaluation, and publication

1. Break the `labeling.llm_pipeline`/`labeling.unitizer_terminal` cycle, then split `llm_pipeline.py` by unitization, structural review, outcome labeling, prompt construction, shard execution/merge, and review application.
2. Split provider caps materialization and provider journaling while preserving authority identity and exact durable records.
3. Split unitization review models, validation, application, terminal handling, and finalization; remove the `unitization.review`/`unitization.unitizer_terminal_review` cycle while retaining `review.py` as the compatibility facade.
4. Split per-case evaluation into config/resume/solver/execution/accounting/publication and spend authorities into protocol/backends.
5. Split official aggregation and shard fan-in into verification, selection, scoring, variance, run-card, storage, and publication layers.
6. Keep frozen protocol codecs in place; split `protocol/freeze.py` only along already-versioned parser/service boundaries with byte-for-byte bundle tests.

### Wave 5: organize multiharness before further growth

1. Check in a multiharness owner/destination manifest covering all 53 current modules.
2. Establish subpackages for contracts/identity, adapters, contained runtimes, materialization, execution, receipts/deliverables, evaluation/scoring, and community publication.
3. Break the oversized runner and command-adapter classes into typed orchestration plus backend implementations without weakening containment, cancellation, evidence, or redaction semantics.
4. Move provider-specific Claude, Codex, OpenAI, and Harvey LAB adapters behind the existing adapter contracts; do not invent a second registry.
5. Preserve installed/local CLI identity, sandbox, tool-exchange, material separation, and receipt compatibility through real fake-binary E2E tests.

Every production slice in Waves 1–5 owns its affected tests: test moves, fixture ownership, compatibility retargeting, and focused validation land with the production seam rather than being deferred.

### Wave 6: converge residual test support and scripts

1. Create narrow test-support packages by domain (`tests/support/<domain>/`) only for reusable builders, captured fixtures, and assertions; no global mutable fixture registry.
2. Split giant test modules not already reduced by their production lane by contract type: domain behavior, persistence/replay, tamper/failure ordering, CLI adapter contract, and explicit E2E scenario.
3. Keep each E2E story whole even when it remains long; extract setup builders and assertion helpers so the test body narrates the scenario.
4. Keep tests parallel-safe with `tmp_path`, `monkeypatch`, ephemeral ports, subprocesses instead of `os.fork()`, and no cross-test shared state.
5. Finish any residual private-CLI patch migration and shrink the compatibility inventory monotonically; the primary migration belongs to the CLI/domain slices that move the owner.
6. Extract containment probe protocols, evidence projection, canaries, and state validation into importable modules, leaving thin Claude/Codex script entry points.
7. Review the four 500–999-line operational scripts and record a seam or cohesion exemption.

### Wave 7: converge and retire migration scaffolding

1. Ensure every file above 500 lines is automatically inventoried and package-lane owned; ensure every manual-disposition case has a live migration bead or reviewed exemption; and remove stale inventory entries after completed moves.
2. Remove temporary compatibility shims, lazy facade probes, and migration-only allowlists whose callers have moved.
3. Recompute the import graph and require no forbidden cycles or reverse adapter dependencies.
4. Run focused checks per slice and the supported full suite once per review-stable head.
5. Run installed wheel/sdist CLI smokes and representative provider-free E2E flows.
6. Update repository maps and contributor guidance, close the organization epics, and retain the architecture ratchet as the regression fence.

## Validation contract for every slice

Before extraction, record the exact reference commit and characterize the affected public/domain behavior. For pure functions this means input/output and exception tests; for stateful and authenticated workflows it includes transaction order, replay, crash/tamper behavior, final byte and namespace checks, and the absence of unintended writes.

Parser/CLI slices additionally retain a structured manifest of command paths, aliases, options, `dest` values, defaults, registration order, and stable logical handler IDs; byte-stable help at a pinned terminal width; the special `freeze` and `publish aggregate` pre-parser bypasses; singleton/`ContextVar`/authority object identity where compatibility requires the same object; exact exit status/stdout/stderr/output-tree behavior; and the absence of extra files. SQLite state comparisons use public snapshot APIs rather than database-file byte equality.

While iterating, run focused domain tests, focused CLI differential tests where applicable, Ruff format/check, Pyright, architecture/import/contract ratchets, and `git diff --check`.

At a review-stable head, run the supported suite once with `uv run pytest -q -n 4 --dist=loadscope`. If parser or packaging changes, also run root/nested help smokes, fixture E2E, package build, and installed wheel/sdist smokes for every affected installed entry point. If an authenticated family moves, run its complete provider-free replay/tamper/TOCTOU corpus and compare exact artifact digests.

No slice is complete merely because imports resolve or tests were divided. It must reduce mixed responsibility, improve dependency direction, preserve behavior, and tighten the architecture inventory.

## Dependency and parallelism strategy

The critical path is:

```text
LegalForecastBench-5qd6.41
  -> legalforecastbench-1t2
  -> LegalForecastBench-cwdv.30
  -> LegalForecastBench-cwdv.14
  -> LegalForecastBench-cwdv.15
  -> {LegalForecastBench-cwdv.17, LegalForecastBench-cwdv.18,
      LegalForecastBench-l8qv.15}
  -> LegalForecastBench-cwdv.16
  -> legalforecastbench-m1pv.8
```

State-store decomposition, non-overlapping package analysis, test-timing characterization, and multiharness planning may proceed in parallel after their own compatibility baselines exist, but two slices that edit the same facade, package `__init__`, baseline, or shared fixture owner must be serialized.

Every implementation bead names its expected file ownership, compatibility obligations, focused validation, full-suite trigger, and dependency edges. Agents claim one bead at a time and do not treat parent/related links as authorization to modify sibling-owned files.

## Beads execution graph

The live tracker expresses this plan without duplicating existing authorities:

- `legalforecastbench-m1pv` — repository-wide coordination epic for non-CLI/non-ingestion lanes.
- `legalforecastbench-m1pv.1` and `.2` — right-sized architecture tooling/inventory and the differential/path/timing baseline.
- `LegalForecastBench-cwdv.30` — residual reverse-CLI-edge removal, with two children.
- `LegalForecastBench-cwdv.14.1` through `.14.6` — six serial verifier/replay-family extractions.
- `LegalForecastBench-cwdv.15.1` through `.15.8` — eight serial command-family/console migrations.
- Existing `LegalForecastBench-cwdv.17`, `.18`, and `.16` — typed stage registry, test decoupling, and final low-hundreds facade.
- `LegalForecastBench-l8qv.15.1` through `.15.13` — ingestion manifest, state-store splits, SCC inversion, vertical slices, and final facade/graph convergence.
- `legalforecastbench-m1pv.3` through `.7` — labeling, unitization, evaluation/publication, multiharness, and residual scripts/tests epics, each with granular implementation children and a capstone.
- `legalforecastbench-m1pv.8` — final repository convergence and migration-scaffolding retirement.

The held source-profile task `legalforecastbench-1t2` now directly depends on `LegalForecastBench-5qd6.41`; CLI verifier work depends on reverse-edge removal; handler work depends on verifier completion; the facade capstone depends on test decoupling; and the stale broad `LegalForecastBench-l8qv.15 -> LegalForecastBench-cwdv` blocker was removed so ingestion can begin after `cwdv.15` while the non-overlapping registry/test/facade capstones proceed. Every code-moving child has its own Cycle 1 gate dependency rather than relying on parent inheritance.

## Definition of done

The repository-wide program is complete when:

- `legalforecast/cli.py` is a small stable facade and no production domain module imports or probes CLI/console adapters.
- Every tracked Python file above 500 lines is automatically inventoried and package-lane owned; every file above 1,000 lines, symbol above 400 lines, forbidden cycle/reverse edge, authenticated-path participant, and similarly high-risk case has either been decomposed or has a reviewed, still-valid cohesion exemption.
- No new module or directory becomes a replacement monolith, and ratchets fail on unreviewed growth.
- `legalforecast.ingestion` and `legalforecast.multiharness` have coherent subpackages with explicit dependency direction and small deliberate `__init__` surfaces.
- Giant stateful classes have focused repositories/services while transaction, authority, replay, and crash-safety semantics remain intact.
- Tests are organized by domain and contract type, private CLI coupling has fallen to a small allowlist, xdist remains parallel-safe, and critical-path runtime has not regressed.
- Operational scripts are thin entry points over importable tested logic or carry reviewed cohesion exemptions.
- Exact authenticated bytes, historical verification, command behavior, provider-spend controls, full suite, static checks, installed-package smokes, and representative provider-free E2E flows all pass.

## Explicit non-goals

This plan does not authorize provider calls, purchases, official freeze/dispatch/publication, credential access, deployment, workflow-file changes, schema/codec changes, semantic feature work, microservices, a monorepo split, or bulk renaming for cosmetic consistency.

Two code-bearing workflow files are explicitly out of scope: `.github/workflows/run-benchmark.yaml` (1,603 lines) and `.github/workflows/official-provider-authority-infra.yaml` (882 lines). Their organization requires a separate human-approved workflow-authority review and must not be smuggled into this Python restructuring program.

It does not require splitting generated code, immutable historical witnesses, or cohesive long tables merely to satisfy a line target; those must still be explicitly inventoried and justified.

It does not replace `LegalForecastBench-cwdv` or `LegalForecastBench-l8qv.15`. The final Beads graph reuses those authorities, adds granular children where the current graph is too coarse, and creates one repository-wide coordination epic for the non-CLI/non-ingestion lanes and convergence criteria.

## Independent audit

An independent read-only worker audited this plan against the reference tree, focused architecture/import/module-map tests, authenticated-path surfaces, installed entry points, current import cycles, and the live Beads graph. Its corrections are incorporated here: right-sized watch-tier handling, architecture-tool self-decomposition, ports/adapters direction, explicit path-sensitive/no-move surfaces, direct Cycle 1 blockers, stateful transaction ownership, missing labeling/disclosure cycles, test co-migration, all installed entry points, workflow exclusions, and repair of stale/unsafe tracker sequencing.

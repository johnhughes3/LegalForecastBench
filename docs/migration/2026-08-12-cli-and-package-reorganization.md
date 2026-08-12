# CLI and package reorganization plan

**Date:** 2026-08-12  
**Status:** proposed; implementation requires approval  
**Tracker:** `LegalForecastBench-cwdv`, `LegalForecastBench-l8qv.15`  
**Change-control gate:** `LegalForecastBench-5qd6.41`

## Outcome

Turn `legalforecast/cli.py` into a stable compatibility facade over small command adapters, move reusable behavior into the domain packages that own it, then reorganize the flat `legalforecast.ingestion` package along its already-documented responsibility boundaries.

This is an incremental, behavior-preserving migration. It is not a rewrite, a command redesign, or a bulk filesystem move. The public executable remains `legalforecast`, the packaging entry point remains `legalforecast.cli:main`, documented invocations remain valid, and historical authenticated artifact bytes and schema semantics remain unchanged. The one necessary post-Cycle-1 source-identity migration is versioned explicitly for newly emitted implementation commitments while every historical mapping remains verifiable.

The migration has two programs with an explicit dependency between them:

1. Thin and modularize the CLI without moving ingestion modules.
2. After the CLI dependency direction is clean, physically organize ingestion modules in cohesive vertical slices.

## Why this work is necessary

At commit `390c6f9`, `legalforecast/cli.py` is 76,043 lines and 3.1 MB. It contains 974 top-level functions, 24 classes, and 210 imports. Its top-level definitions include:

- A 1,794-line `build_parser()`.
- 173 argument-builder functions totaling 7,690 lines.
- 167 command handlers totaling 27,064 lines, including 105 acquisition handlers.
- 160 `_verify_*`, `_validate_*`, `_require_*`, and `_guard_*` functions totaling 14,893 lines.
- Domain dataclasses, replay machinery, artifact serialization, authenticated lineage verification, provider orchestration, and fixture construction.

The problem is therefore not mainly argparse. Moving the same bodies into one `commands.py` file, or mechanically spreading them across `commands/*.py`, would preserve the coupling under different filenames.

The module is also an accidental internal API:

- A direct AST inventory finds 100 test/support files importing `legalforecast.cli` and 47 consuming private CLI names.
- The same strict inventory finds 481 explicit `monkeypatch.setattr` calls through a CLI module alias, across 182 attributes in 39 files. Broader string-target and indirect patch patterns will be recorded in the compatibility inventory rather than mixed into this baseline.
- Three production modules depend upward on CLI state, creating dependency cycles or runtime coupling:
  - `legalforecast/ingestion/purchase_approval.py`
  - `legalforecast/ingestion/recovered_public_replay.py`
  - `legalforecast/ingestion/resolved_post_recovery.py`

The first and third modules use direct lazy imports. `recovered_public_replay.py` instead locates the CLI dynamically and probes its globals to preserve legacy monkeypatch behavior.

The broader package has a second organization problem. `legalforecast.ingestion` contains 143 top-level implementation modules excluding `__init__.py`, and about 142,000 lines in one mostly flat directory. Its 613-line `__init__.py` eagerly imports 32 modules and exposes 274 names. There are 438 internal ingestion dependency edges and two cyclic components, including a 16-module purchase/recovery/disclosure authority knot. Bulk moves would be unsafe.

## Existing work to preserve

Do not create another refactor epic. The Beads graph already has the correct umbrella and much of the intended sequencing:

- `LegalForecastBench-cwdv.13` completed the first narrow recovery/clearance replay extraction.
- `LegalForecastBench-cwdv.14` covers remaining verifier and replay families.
- `LegalForecastBench-cwdv.15` covers stage-sized handler relocation.
- `LegalForecastBench-cwdv.17` covers a typed CLI/orchestrator stage registry.
- `LegalForecastBench-cwdv.18` covers test decoupling and measured test bottlenecks.
- `LegalForecastBench-cwdv.16` is the thin-CLI capstone.
- `LegalForecastBench-l8qv.15` already covers later ingestion-internal decomposition.

The successful pattern from PR #579 (`9a22e98`) should be retained: extract one cohesive family, leave a small compatibility adapter, update focused tests and the ingestion map, and run the full suite only at a review-stable head. Its follow-up PR #583 supplies an equally important lesson: domain APIs must not leak `CommandError`, and extracted domain modules must not retain lazy runtime imports of the CLI.

## Architectural rules

The target dependency direction is:

```text
legalforecast.cli facade
        |
        v
legalforecast.console adapters
        |
        v
domain services and models
        |
        v
contracts / protocol / shared primitives
```

The following rules are structural acceptance criteria:

1. `legalforecast/cli.py` remains the stable import and executable facade.
2. `legalforecast.console` owns argparse registration, `Namespace` translation, dispatch, and CLI error rendering only.
3. Domain packages own verifiers, replay, artifact construction, provider operations, dataclasses, and state transitions.
4. No production domain module imports `legalforecast.cli` or `legalforecast.console`, at import time or call time.
5. Command adapters may depend on domain APIs; domain APIs may not depend on command adapters.
6. Domain APIs raise typed domain errors. The console boundary translates them into stable exit codes and stderr.
7. Authority tokens, `ContextVar` instances, issue/consume closures, and other identity-sensitive objects move atomically and are re-exported as the same object when temporary compatibility requires it.
8. No generic command framework is introduced. Each command family exposes a small registrar and thin handlers.
9. Existing coherent top-level packages remain intact: `contracts`, `evals`, `extraction`, `labeling`, `multiharness`, `protocol`, `publication`, `reporting`, `selection`, and `unitization`.

## Target layout

`legalforecast/cli.py` and a `legalforecast/cli/` directory cannot coexist. Keep the module as the permanent public facade and use `legalforecast.console` for internal adapters.

```text
legalforecast/
├── cli.py                         # stable facade: main, build_parser, CommandError
├── console/
│   ├── __init__.py                # inert; no eager command imports
│   ├── app.py                     # pre-parser dispatch, parse, invoke, error boundary
│   ├── errors.py                  # CommandError and CLI-only translation helpers
│   ├── parser.py                  # root parser and registrar composition
│   └── commands/
│       ├── benchmark.py           # discover, retrieve, extract, link, score, report
│       ├── evaluation.py          # model/eval execution adapters
│       ├── publication.py
│       ├── fixtures.py
│       ├── pilot.py
│       ├── multiharness.py
│       ├── batch_002.py
│       └── acquisition/
│           ├── lifecycle.py       # config, lineage, run/init cycle
│           ├── discovery.py       # Case.dev, Firecrawl, CourtListener, RECAP
│           ├── screening.py
│           ├── cohort.py
│           ├── purchase.py
│           ├── recovery.py
│           ├── disclosure.py
│           ├── documents.py       # retrieval, parse, materialization
│           ├── unitization.py
│           ├── labeling.py
│           ├── packets.py
│           └── finalization.py
├── ingestion/                     # domain implementation; initially keep paths stable
├── labeling/
├── unitization/
├── evals/
├── publication/
└── reporting/
```

Each command module should normally remain below roughly 500 lines. If a registrar is larger, split it by the command taxonomy rather than by arbitrary line ranges. Handler bodies should usually be small enough to read without scrolling through domain algorithms.

After the CLI program is complete, the eventual ingestion taxonomy is:

```text
legalforecast/ingestion/
├── __init__.py                    # compatibility exports during migration
├── canonical_json.py              # retain frozen path
├── provenance.py                  # retain foundational path in this reorganization
├── http_config.py                 # retain foundational path in this reorganization
├── providers/
│   ├── case_dev/
│   ├── courtlistener/
│   │   └── recap/
│   └── firecrawl/
├── cycle/
├── documents/
├── screening/
├── disclosure/
└── recovery/
    ├── selection/
    ├── documents/
    └── authority/
```

This taxonomy is a provisional destination, not one pull request. `docs/ingestion-module-map.md` already assigns each module to one of ten concerns and supplies the ownership vocabulary, but its concerns do not map one-to-one onto these directories. Phase 7 must remeasure the graph and add an explicit module-to-destination manifest before any physical move.

## Compatibility contract

The following interfaces remain stable throughout the migration:

- The `legalforecast` executable.
- `legalforecast.cli:main` in `pyproject.toml`.
- `legalforecast.cli.main`, `legalforecast.cli.build_parser`, and `legalforecast.cli.CommandError`.
- Command paths, aliases, options, `dest` names, defaults, selected handler behavior, help meaning, exit codes, stdout, and stderr.
- Exact authenticated output bytes, output ordering, file paths committed by existing cards, resume/idempotency behavior, and absence of unexpected files.
- The special pre-parser handling for `freeze` and `publish aggregate` until those commands have their own separately characterized migration.

Temporary private re-exports from `legalforecast.cli` are allowed only for an explicitly inventoried compatibility caller. They should carry a removal issue and must not become a permanent mirror of hundreds of implementation details.

For ingestion filesystem moves, preserve only deliberate supported import surfaces:

- Names exported by `legalforecast.ingestion.__all__` remain compatible until a versioned deprecation removes them.
- Repository-internal direct module imports move to the new owner in the same slice.
- Old direct module paths receive forwarding shims only when they are documented, externally supported, dynamically imported, serialized by qualified name, or otherwise proven necessary.
- A forwarding shim does not promise monkeypatch-through-old-module semantics. Tests should patch the new owner or use injected collaborators.
- Module-object identity is tested and preserved only where the compatibility inventory identifies it as part of the contract.

## Migration phases

### Phase 0: approve and repair the execution graph

No code migration begins until `LegalForecastBench-5qd6.41` closes. That gate is the final Cycle 1 freeze, eight-shard official dispatch, receipt fan-in, and publication—not merely acquisition completion.

After approval:

1. Make `cwdv.15` depend on, and therefore be blocked by, `cwdv.14` (`bd dep add LegalForecastBench-cwdv.15 LegalForecastBench-cwdv.14`); both currently become available together and both substantially edit `cli.py`.
2. Make `cwdv.16` depend on `cwdv.18` (`bd dep add LegalForecastBench-cwdv.16 LegalForecastBench-cwdv.18`). The intended order is `cwdv.14 -> cwdv.15 -> {cwdv.17, cwdv.18} -> cwdv.16`, so the facade capstone follows both stage metadata and test decoupling.
3. Split `cwdv.14` into verifier/replay-family children.
4. Split `cwdv.15` into stage-sized command children.
5. Give every child its target modules/APIs, compatibility policy, focused tests, expected `cli.py` reduction, and exact-byte preservation requirement.
6. Do not create a new umbrella or duplicate `l8qv.15`.

### Phase 1: characterize contracts and add architecture ratchets

Before moving behavior:

1. Generate a reviewed structured command manifest from `build_parser()` containing every command path, alias, option, destination, default, and stable logical handler ID. Python `__module__` and `__qualname__` are inventory data, not permanent compatibility promises, because handler ownership will intentionally move.
2. Capture selected help snapshots for the root, acquisition, batch-002, and representative nested families.
3. Establish a small curated provider-free differential corpus for deterministic command families. Normalize only explicitly non-contract fields; focused golden and domain tests remain the default proof for commands with time, environment, or service-derived output.
4. Check in a generated compatibility inventory covering facade-only imports, private imports, module-attribute and string monkeypatches, callable/module identity assertions, `cli.__file__` assumptions, dynamic imports, and `__module__ == "legalforecast.cli"` checks. Every slice must show that no stale old-owner patch or identity assertion remains.
5. Establish a reviewed test-import baseline for private `legalforecast.cli` use and shrink it in every later slice.
6. Add a production forbidden-import ratchet with an exact allowlist for the three current upward dependencies. Phase 3 must shrink that allowlist to zero; it may never grow.
7. Add the missing structural baseline for `cli.py` size and definition categories. Keep it separate from `legalforecast/contracts/ratchet.py`, whose findings concern commitment and schema contracts rather than source organization.
8. Record the authenticated implementation-source profiles that name or hash `legalforecast/cli.py`; do not silently rewrite them during extraction.

Implement the structure, import, and compatibility checks in `legalforecast/testing/architecture.py`, store the reviewed generated data in `legalforecast/testing/architecture_baseline.json`, and enforce them in `tests/test_architecture.py`. This pytest test is the authoritative architecture gate and therefore already runs in the supported local suite, `scripts/release_check.py`, and CI without a workflow edit. A future standalone fast gate is optional and would be a separate workflow-authority change.

### Phase 2: decouple authenticated implementation identity

The current Firecrawl screening implementation identity hashes the entire physical `legalforecast/cli.py`. Ordinary CLI edits would therefore churn newly generated authenticated source identities even when the moved behavior is unrelated.

After Cycle 1 closes and before ordinary extraction:

1. Add an explicit versioned implementation-source profile whose current source set names the narrow screening, registrar, and verifier owners rather than the whole CLI facade.
2. Continue accepting every historical compatible source mapping required to verify frozen artifacts.
3. Characterize and test the migration independently of command or verifier semantics.
4. State the distinction precisely: historical authenticated artifacts and their bytes remain unchanged and verifiable; newly emitted implementation-source commitments necessarily use the new versioned profile.

### Phase 3: remove production reverse dependencies

Do this before parser or handler relocation.

1. Move `verify_completed_target_cohort_projection_for_purchase_approval` out of `cli.py` into a neutral target-projection verification API, owned by the target-cohort domain. Update `purchase_approval.py` and the CLI to import that API. Temporarily re-export the same callable from `cli.py` only if an inventoried caller needs it.
2. Move authenticated-clearance replay verification into the provenance/clearance domain. Update `resolved_post_recovery.py` and the CLI to depend on it.
3. Replace `recovered_public_replay._cli()` and all runtime CLI probing with a typed dependency bundle or explicit collaborators. The default production bundle is built from domain functions, not CLI globals.
4. Move any singleton authority objects with their owning family; do not duplicate them in adapters.
5. Expand `tests/test_ingestion_import_cycles.py` into a forbidden-edge and multiple-import-order regression.

This phase is complete when no production file below `legalforecast/` imports `legalforecast.cli` except `cli.py` itself, and no domain behavior relies on monkeypatching CLI globals.

### Phase 4: extract verifier and replay families

Execute `cwdv.14` bottom-up in cohesive batches. The initial family manifest should include:

1. Target/cohort projection and materializer verification.
2. Recovery, purchase-journal, replacement-source, and successor-history replay.
3. Disclosure and provenance-clearance run-card verification.
4. Screening, discovery, and acquisition run-card verification.
5. Stage A/unitization replay and provider-review verification.
6. Packet-input, packet-build, corpus-finalization, and downstream-lineage verification.

Place each function, dataclass, and helper with the domain that owns its vocabulary. Create a focused `*_replay.py` or `*_verification.py` module when putting the code into an already-large implementation module would create another monolith.

For every family:

- Characterize the domain return value and exception type. Pin an exact domain exception message only when it is deliberately supported or externally observed.
- Characterize CLI exit code and stderr separately.
- Preserve final byte, namespace, and TOCTOU rechecks.
- Update only exact affected entries in `contracts/ratchet_baseline.json` according to the ratchet tool's semantics. Move a path-keyed entry when the same finding moves; delete it only when the finding is eliminated. Introduce a named contract profile only where the contract system requires one, and never regenerate the baseline wholesale.
- Update the structural and private-import baselines monotonically.

### Phase 5: move command families atomically

Create `legalforecast.console` in command-family slices. Each slice moves its parser registration, thin console adapter, remaining domain body, tests, monkeypatch targets, and static-check ownership together. `legalforecast.console` must never import handlers from the facade; otherwise `cli -> console -> cli` recreates the dependency cycle.

Migrate in this order:

1. Existing bounded registrars: multiharness, acquisition completion summary, exact-100 successor commands, and supporting-document successor commands.
2. Core benchmark, evaluation, publication, fixture, and pilot commands.
3. `batch-002`.
4. Acquisition lifecycle and lineage.
5. Acquisition discovery and screening.
6. Acquisition cohort and selection.
7. Purchase, recovery, and disclosure.
8. Documents, parsing, unitization, labeling, packets, and finalization.

Each command module exposes a plain `register(subparsers)` function. Root composition stays explicit in `console/parser.py`. Prefer normal imports. Introduce lazy imports only for a measured expensive family, and require an installed-package smoke that resolves every registered handler module so missing modules and import cycles cannot hide until command execution.

Keep the `freeze` and `publish aggregate` pre-parser bypasses unchanged in `legalforecast/cli.py` initially. Move either bypass into `console/app.py` only as its own atomic, characterized slice; never absorb it accidentally into ordinary registrar work.

Execute `cwdv.15` in the stage-sized order above. Each migration unit moves three layers deliberately:

1. Domain behavior to its domain service, if it has not already moved.
2. A thin `Namespace`-to-typed-call adapter to `legalforecast.console.commands`.
3. Tests and monkeypatches to the new owner or explicit injected collaborator.

Do not leave artifact serialization, provider loops, replay verification, or state transitions in command modules. Do not rename commands or rewrite their semantics while moving them.

Suggested execution children are:

- Core/eval/report/publication/fixture/pilot.
- Batch-002 discovery and screening.
- Acquisition lifecycle, lineage, discovery, and screening.
- Cohort projection, selection, and materialization.
- Purchase, recovery, and disclosure.
- Document retrieval, parse, and packet inputs.
- Unitization and labeling.
- Packet build, finalization, and rehearsal.

### Phase 6: unify stage metadata and finish the facade

After handler relocation:

1. Implement the narrowly scoped typed stage registry from `cwdv.17` where CLI and orchestration genuinely duplicate stage metadata. Do not force unrelated commands into it.
2. Finish `cwdv.18`: domain tests call typed APIs and patch domain owners; only a reviewed CLI-contract allowlist imports the facade.
3. Reduce `legalforecast/cli.py` to imports/re-exports of `main`, `build_parser`, and `CommandError`, plus documented temporary aliases.
4. Keep `pyproject.toml` unchanged.
5. Ratchet the facade to a small fixed ceiling and prohibit domain definitions there.
6. Remove temporary aliases only after all repository callers migrate and any supported compatibility period ends.

The goal is a facade measured in tens or low hundreds of lines, not the older 10,000-line parser target. Total console registration may be several thousand lines, but it is partitioned by stable command families and contains no domain algorithms.

### Phase 7: reorganize ingestion by vertical slice

Only begin `l8qv.15` after command-handler relocation (`cwdv.15`) is complete, all upward CLI dependencies are gone, and the import graph is remeasured. The typed registry, test-decoupling, and final facade capstone may continue in parallel only if file ownership and validation remain non-overlapping.

1. Inventory documented/public imports, dynamic imports, qualified-name serialization, and module-identity dependencies, then check in an explicit current-module-to-destination manifest.
2. Add import-boundary checks for the intended ingestion layers.
3. Pilot one low-coupling cohesive move: `case_dev_scheduling.py` to `providers/case_dev/scheduling.py`. Preserve the old path only to the degree required by the compatibility inventory.
4. Move provider families one vertical slice at a time: Case.dev, CourtListener/RECAP, then Firecrawl. Do not move unrelated low-degree leaves together merely to populate directories.
5. Move document planning/materialization and screening after provider dependencies settle.
6. Break cyclic components through explicit typed interfaces before moving their files.
7. Move cycle, disclosure, purchase, and recovery authority modules last.
8. Shrink `ingestion/__init__.py` only after consumers import narrow owner modules. Do not turn it into another eager dispatcher.

Never combine a filesystem move, large-module split, and semantic cleanup in one pull request. A move first establishes a stable path; a later measured task may split a large module along proven interfaces.

## Files and call sites requiring coordinated updates

The following list is part of the migration contract; each implementation child selects the relevant subset.

| Surface | Required update |
| --- | --- |
| `legalforecast/cli.py` | Replace each moved family with facade exports or thin dispatch. |
| `legalforecast/console/**` | Add parser registrars, thin handlers, and the CLI error boundary. |
| `legalforecast/testing/architecture.py` | Generate and validate structure, import, and compatibility inventories. |
| `legalforecast/testing/architecture_baseline.json` | Store the reviewed, monotonically shrinking architecture baseline. |
| Domain modules | Own typed services, verifiers, replay, dataclasses, and domain errors. |
| `legalforecast/ingestion/purchase_approval.py` | Remove lazy CLI verifier import. |
| `legalforecast/ingestion/recovered_public_replay.py` | Remove `_cli()` and runtime CLI-global resolution. |
| `legalforecast/ingestion/resolved_post_recovery.py` | Remove lazy CLI clearance-verifier import. |
| `pyproject.toml` | Keep `legalforecast = "legalforecast.cli:main"`; change only if a separately approved public migration is desired. |
| `tests/conftest.py` | Replace CLI-private fixtures and patches with domain fixtures/collaborators. |
| CLI-importing tests | Retain facade imports only for CLI contracts; move domain assertions and patches to owners. |
| `tests/test_cli_orchestration.py` | Pin parser tree, handler dispatch, aliases, and help contracts. |
| `tests/test_cli_failure_modes.py` | Pin error translation, exit status, and stderr. |
| `tests/test_cli_coverage_review.py` | Retain representative fixture-backed end-to-end paths. |
| `tests/test_ingestion_import_cycles.py` | Enforce forbidden reverse imports and import-order safety. |
| `tests/test_ingestion_module_map.py` | Update every physical ingestion move. |
| `tests/test_architecture.py` | Authoritative architecture ratchet in the supported pytest suite. |
| `tests/test_contract_ratchet.py` | Preserve path-keyed baseline semantics during moves. |
| `tests/test_package_skeleton.py` | Update installed import and facade-help coverage. |
| `tests/test_official_run_runbook.py` | Continue validating documented acquisition commands against the parser. |
| `tests/test_release_check.py` | Update only if release-check orchestration changes. |
| `tests/test_ci_workflow.py` | Update only if a direct standalone CI architecture gate is added. |
| `docs/ingestion-module-map.md` | Remain the authoritative move manifest and navigation map. |
| `docs/README.md` | Keep this retained migration plan discoverable. |
| `scripts/verify_review_blockers.py` | Replace hard-coded `cli.py` scans with explicit owning module sets. |
| `legalforecast/contracts/ratchet_baseline.json` | Move/delete only exact matching path-keyed exceptions as code moves. |
| `legalforecast/ingestion/firecrawl_screening_identity.py` | Version authenticated implementation-source sets explicitly when ownership changes. |
| `legalforecast/ingestion/screening_union_policy_rebind.py` | Update source identity only in the same explicit migration. |
| `tests/ingestion/test_firecrawl_screening_identity.py` | Pin the versioned source-set migration. |
| `tests/fixtures/official_community_import_budget.json` | Update when multiharness reverse-import ownership changes. |
| Package-root tests using `cli.__file__` | Use `legalforecast.__file__` or `importlib.resources`. |
| `scripts/release_check.py` | No direct change is required while `tests/test_architecture.py` is authoritative and covered by the supported suite. |
| CI workflow | No edit is required merely to add pytest-collected architecture tests; any direct workflow gate is a separate workflow-authority change. |

## Validation strategy

Every extraction or move selects the checks applicable to its risk from the same evidence ladder. Exact-byte, namespace, tamper, and TOCTOU checks are mandatory whenever a slice crosses an authenticated artifact or authority boundary; a pure parser registrar or isolated leaf move does not need unrelated recovery checks.

### Before the change

1. Freeze the exact reference commit.
2. Select a provider-free argv corpus for the family: valid execution, malformed input, missing input, resume/idempotency, and tampered commitment.
3. Record parser metadata and selected help output.
4. Record the expected relative output tree and exact artifact digests.
5. Record canonical state through production snapshot APIs; do not compare SQLite database files byte-for-byte.

### While iterating

1. Run focused domain tests.
2. Run focused CLI differential tests in isolated subprocesses or installed checkouts.
3. Compare exact exit status, stdout bytes, stderr bytes, relative output tree, artifact bytes/SHA-256, and absence of unexpected files.
4. Run domain exception-boundary tests and CLI translation tests separately.
5. Run family-specific tamper, final-byte, namespace, and TOCTOU regressions.
6. Run Ruff format/check and Pyright for the changed slice.
7. Run contract, structure, import-boundary, and module-map ratchets.

### At a review-stable head

1. Run the recovery capsule and cycle-preflight/rehearsal tests relevant to the moved family.
2. Run the supported suite once: `uv run pytest -q -n 4 --dist=loadscope`.
3. When parser or entry-point wiring changes, run root and nested CLI help smokes, fixture E2E, package build, and installed wheel/sdist CLI smokes.
4. Run `git diff --check`.

## Definition of done

The CLI program is complete when:

- `legalforecast/cli.py` is a small facade with no domain dataclasses, verifiers, provider orchestration, artifact serialization, or state transitions.
- `legalforecast.console` contains only registration, argument translation, dispatch, and error rendering.
- No production domain module imports `legalforecast.cli` or `legalforecast.console`.
- Every node in the frozen Phase 1 command manifest and its documented behavior remains available.
- The private CLI test-import baseline has fallen to a reviewed CLI-contract allowlist.
- Structural and import-boundary ratchets prevent regression.
- Exact artifact bytes, resume behavior, CLI outputs, full suite, static checks, preflight/rehearsal, and installed-package smokes pass.

The package-organization program is complete when:

- `legalforecast.ingestion` is physically organized by the revalidated module-to-destination manifest derived from the documented ownership taxonomy.
- Cyclic authority components were broken through explicit interfaces before file moves.
- Supported imports have compatibility coverage and internal callers use narrow owner modules.
- `ingestion/__init__.py` is a small deliberate facade rather than a 274-name eager aggregation point.
- No directory becomes a replacement monolith, and any remaining files above roughly 1,000 lines have a documented cohesion reason or a separate measured split issue.

## Explicit non-goals and no-move zones

This plan does not authorize:

- Any provider call, purchase, official freeze, dispatch, publication, or credential access.
- Changes to frozen canonical JSON, manifest/freeze codecs, commitment forms, schema semantics, or preflight behavior.
- A large-scale rename of historical `exact100_*`, `exact310_*`, or `target_*` modules for cosmetic consistency.
- Movement of `legalforecast.ingestion.canonical_json`, `legalforecast.ingestion.provenance`, `legalforecast.ingestion.http_config`, or `legalforecast.protocol.manifest`.
- Movement of `cycle_preflight.py`, `cycle_preflight_manifest.py`, or `cycle_lineage_index.py` during this reorganization; any such move requires a separate, versioned public-entry-point and authenticated-contract migration.
- Movement of the 16-module purchase/recovery/disclosure authority cycle before its dependencies are inverted.
- Movement of `infisical_systemd_launcher.py`, an installed operational entry point, merely because it has low graph degree.
- Editing the historical source witness `legalforecast/data/rest_observation_policy_rebind_old_source_v1.txt`.
- Reorganizing tests by file size alone.
- Combining reorganization with feature work or semantic cleanup.

## Recommended first implementation unit

After approval, tracker repair, and closure of `LegalForecastBench-5qd6.41`, use three separately reviewable units:

1. Land only the minimum Phase 1 architecture baseline, compatibility inventory, and focused characterization required for the first domain seam.
2. Land the versioned authenticated implementation-source decoupling without changing command or verifier semantics.
3. Extract the purchase-approval target-projection verifier, remove its reverse dependency, and decrement the baselines. It has a clear ownership defect and establishes the domain/CLI exception boundary for later families.

Defer general command manifests, help snapshots, and differential cases that the first seam does not exercise until the parser/command migration needs them.

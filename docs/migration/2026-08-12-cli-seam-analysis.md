# CLI seam analysis: empirical companion to the reorganization plan

**Date:** 2026-08-12
**Status:** analysis artifact; supports, and defers to, the [CLI and package reorganization plan](2026-08-12-cli-and-package-reorganization.md) (the program of record)
**Reference commit:** `390c6f9`

This document records deterministic measurements of `legalforecast/cli.py`, probe-verified extraction mechanics, one optional transitional compatibility device, and slice-sizing data for the program of record's Phase 5 ordering. It proposes no alternative architecture and authorizes no work.

## Method

A stdlib-`ast` walker over `legalforecast/cli.py` collected every top-level symbol with its line span, built the symbol-to-symbol reference graph, seeded command groups from `_cmd_*` handlers and `_add_*_arguments` registrars matched against the `build_parser()` top-level command list, and propagated group reachability transitively. Test-surface inventories came from repository-wide structural greps. The walker is ~150 lines and regenerable from this description; the Phase 1 command manifest and architecture baseline supersede it as durable tooling.

**Known limitation:** the monkeypatch inventory here matched only the literal `monkeypatch.setattr(cli, "name", ...)` alias form. The program of record's AST inventory (481 `setattr` calls across 182 attributes in 39 files) supersedes these counts; the deltas are alias variants and indirect patterns this grep missed. The name-level lists below remain useful as a lower bound and as seed data for the Phase 1 compatibility inventory.

## Measurements at `390c6f9`

**Scale and churn**

- 76,043 lines; 1,060 top-level symbols; 210 import statements; 173 `add_parser` sites; 152 `set_defaults(handler=...)` bindings.
- 269 of the 581 commits in the trailing three months touched `cli.py` — the file is the dominant merge-conflict surface for parallel agents, which is the operational cost the migration removes.

**Import surface (tests)**

- 111 test files import `legalforecast.cli`; 58 import only `main`. Beyond `main`/`build_parser`/`CommandError`, tests import a small set of private names directly and access 277 distinct attributes on the module object.
- 80 distinct names are monkeypatched via the literal `cli` alias form (lower bound; see limitation above). Placement: 42 are defined in acquisition-group code, 35 are names `cli.py` imports from domain modules, 3 are cross-group utilities.

**Structure**

- Cross-group shared layer: 139 symbols, 4,914 LOC, dominated by IO/logging utilities (`_log_event` used by 14 groups, `_write_json` 13, `_read_records` 12, `_write_dry_run_plan` 12).
- Handler-to-handler calls: only 8 edges repository-wide — there is no orchestration hub; coupling flows through the shared utility layer, not between commands.
- Non-acquisition top-level groups are small: `unitize` (115 exclusive LOC), `report` (77), `score` (53), `link` (42), `extract` (37), `retrieve` (36), `smoke` (29), `discover` (23), `label` (21), `publish` (16), plus registration code. These are hours-sized template-proving slices.
- `batch-002` registration is ≈1,100 lines and its handler bodies interleave heavily with acquisition helpers; it is correctly sequenced in the program of record as its own family before the acquisition slices.
- Acquisition dominates: ~105 of 152 handler bindings and ≈67,000 LOC of group-exclusive code.

**Acquisition internal density (negative result worth keeping)**

Transitive-closure analysis shows almost every acquisition helper is reachable from three or more handlers; weighted community detection over the co-reference graph returns either one blob or singletons. There is **no clean graph-derived partition** of acquisition. Practical consequence for Phase 5: place each helper with its dominant direct user, accept an explicit intra-acquisition `_common` layer, and treat residual cross-module imports inside the acquisition command family as acceptable. Domain-noun bucketing yields workable slice sizes (direct-reference placement, LOC approximate):

| Bucket (maps onto plan's `commands/acquisition/*`) | LOC |
| --- | --- |
| discovery (Case.dev, Firecrawl, CourtListener/RECAP, screening) | ≈10,200 |
| target cohort / selection | ≈9,200 |
| replacement / clearance | ≈5,200 |
| unitization & attorney review | ≈4,800 |
| documents / decision texts / packets / materialization | ≈3,500 |
| promotion / sealing / ranked subsets | ≈2,900 |
| purchase / ledger / budget | ≈2,400 |
| disclosure | ≈2,300 |
| lifecycle / lineage / successor | ≈2,000 |
| labeling / batons | ≈1,500 |
| recovery | ≈500 |
| downloads, finalization, rehearsal, misc | ≈6,100 |
| shared within acquisition before second-level placement | ≈16,600 |

The ≈16.6k "shared" figure shrinks substantially when placement is applied transitively; what remains genuinely multi-bucket becomes the family's `_common` module(s).

**Confirmed upward dependencies and identity constraint**

- `ingestion/purchase_approval.py:345` and `ingestion/resolved_post_recovery.py:1058` lazily import `legalforecast.cli`; `ingestion/recovered_public_replay.py` resolves the CLI dynamically and checks `__module__ == "legalforecast.cli"` (line 734). Phase 3 of the program of record removes all three.
- `ingestion/firecrawl_screening_identity.py` pins `legalforecast/cli.py` as a hashed implementation-source path in multiple entries. **Any edit to `cli.py` churns newly emitted authenticated source identities, and replacing the module with a package would break the pinned path outright.** This independently confirms the program of record's sequencing: no code migration before the Cycle 1 gate closes and Phase 2 decouples source identity.

**Not-dead code caution**

Five defs are unreachable from any CLI seed (`_consolidated_resolved_capability_boundary`, `_direct_queue_delivery_lineage`, `_recovered_public_lineage_digest`, `_replacement_budget_operation_pairs`, `_verified_snapshot_raw_html_sources`; 331 LOC total). At least one is imported directly by tests. These are test-only or latent surface — record them in the compatibility inventory; do not delete on reachability evidence alone.

## Probe evidence (evidence-only branch)

Branch `scratch/cli-demonolith-probe` (commits `6765fa8`, `4a6724b`) mechanically extracted the `score` command family behind a facade. It is **not** a candidate first PR — it converts `cli.py` into a package, which conflicts with the program of record's module-facade decision and with the pinned source-identity path above. The branch exists to validate mechanics and should be deleted after its lessons are harvested into Phase 1/5 implementation. Verified findings, all applicable to `legalforecast.console`:

1. **Registrar extraction is byte-clean.** Moving a family's parser wiring into a `register(subparsers)` function called at the original registration point, with registration order preserved, left top-level and subcommand `--help` output byte-identical and focused-suite pass counts unchanged (63/63). Registration order is what preserves help text and prefix-matching behavior; help goldens (with pinned `COLUMNS`) are the cheap drift gate.
2. **Patch-through-facade can be preserved when wanted.** A test that monkeypatches a helper on the facade module and runs the moved handler passes when the moved call site references the helper through a module-namespace alias (`from legalforecast import cli as _cli_ns; _cli_ns._read_records(...)`). This late-binding survives module initialization order and needs no test edits.
3. **Static-gate mechanics.** In facade context, ruff requires the explicit re-export idiom (`from x import name as name`) once a name's last local use moves out — which is exactly the facade convention. Pyright strict flags cross-module private-name use; a scoped `[[tool.pyright.executionEnvironments]]` entry for the console tree (disabling only `reportPrivateUsage` there) keeps the rule live everywhere else. Expect both when implementing Phase 5 and encode them in the slice template.

## Optional transitional device: patch-through-facade per slice

The program of record's destination is right: tests patch the new owner, and the compatibility inventory drives stale patch targets to zero (`cwdv.18`, Phase 6). For a **large** slice where migrating its share of the 481 `setattr` calls in the same PR is the schedule bottleneck, finding 2 above gives a probe-verified middle path: the slice moves code while its inventoried patched names temporarily remain facade-bound and are referenced through the facade namespace at moved call sites. Constraints mirroring the plan's temporary-re-export policy: only names on the compatibility inventory's patch list; each use carries a removal issue; the inventory tracks the count monotonically to zero. This decouples "move the code" from "migrate the tests" without the vacuous-pass risk of a missed patch retarget. Whether any slice uses it is an implementation choice per slice, not a plan change.

## Sequencing implications for "how fast can this go"

The critical path is serial until families unlock: gate closure (`LegalForecastBench-5qd6.41`) → minimal Phase 1 baseline/inventory → Phase 2 source-identity decoupling → Phase 3 reverse-dependency removal. After that, Phase 5 families pipeline quickly:

- The ten small top-level families are hours-sized each and prove the slice template.
- `batch-002` is a small-days slice (registration-heavy, bodies shared with acquisition).
- Acquisition is the long pole (~67k LOC across the bucket table above); its eight ordered slices in the program of record are each bounded by the bucket sizes here.
- Every slice edits the facade file, so facade edits serialize; parallel agent capacity belongs to verification and to Phase 4 domain push-down (which edits domain modules, not the facade) rather than concurrent facade edits. The contract-ratchet baseline behavior (whole-tree; any main merge invalidates open ratchet-touching PRs) is another reason to keep slices small and land them within hours.

## Provenance

Produced by a scoped quick-mode de-monolithization analysis run (analysis and planning only; no execution authorized or performed against mainline). Defaults chosen without interactive confirmation: quick mode scoped to `cli.py` plus a repo census; degraded toolchain (stdlib AST walker in place of the full census toolchain); probe confined to the evidence-only branch named above. All numbers are reproducible from the method description at commit `390c6f9`.

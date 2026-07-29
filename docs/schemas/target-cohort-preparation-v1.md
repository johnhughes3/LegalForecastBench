# Target-cohort preparation v1

`legalforecast acquisition prepare-target-cohort --target-case-count N` is the generic, provider-safe preparation driver for a complete saturated acquisition snapshot. The caller must provide `--expected-snapshot-manifest-sha256` from an externally frozen SHA-256 of that snapshot's `manifest.json`; preparation and its public-download planning stage fail before trusting lineage if the manifest bytes drift.

The command carries every viable snapshot candidate through public-document planning, free downloads, authoritative CourtListener REST gap resolution, newly-free recovery, core-document filtering, and disclosure-review input generation.

It never invokes RECAP Fetch, acknowledges PACER fees, or purchases a document.

CourtListener is the authoritative source for document resolution.

Case.dev is permitted only upstream for an equivalent noncharging lookup, and Firecrawl is permitted only when a documented CourtListener decision-search surface is unavailable through the supported API.

## Frozen configuration

`target-cohort-config.json` uses `legalforecast.target_cohort_config.v1` and binds the explicit positive `target_case_count`, snapshot manifest and screened-case hashes, cycle and batch identity, provider mode, rate profile, costs, caps, output paths, and semantic child-stage commands.

Its `config_sha256` is the canonical JSON hash of every other field.

Changing the target, source, cap, or path on resume fails before any child provider can be constructed.

## Complete candidate frontier

`05-budget/full-candidate-frontier.json` uses `legalforecast.target_cohort_candidate_frontier.v1`.

Its self-hashed policy contains:

- `target_case_count`, `candidate_count`, and `selected_candidate_count`;
- `frontier_truncated: false`;
- exact hashes for the snapshot manifest, preparation config, reconciled CourtListener selection, case relevance, merged download manifest, core-filter results, provisional budget, restriction evidence, and disclosure-review requests;
- every candidate in canonical missing-core cost order, including intrinsically excluded candidates;
- purchase-document IDs and roles, estimated cost, exclusion reasons, selection status, court, NOS macro category, related-case family, and MDL family.

The frontier join is fail-closed: duplicate IDs or any difference between resolved selection IDs and core-filter candidate IDs aborts preparation.

Case relevance must cover the resolved selection exactly.

Download-manifest candidates must belong to that selection, and restriction-evidence and disclosure-review-request document keys must each equal the complete manifest key set.

The frontier's `clearance_contract` freezes the required `clear-disclosures` run-card schema and executed state, the expected manifest and restriction hashes, authenticated `reviews` and `review_receipt` source commitments, the `disclosure_clearance` output commitment, review-authority fields, and a rule forbidding orphan clearance rows.

Because clearance occurs after preparation, the frontier cannot contain the future review or clearance hashes.

A downstream extension must verify the actual completed clearance run card against this contract and reject every clearance row whose candidate/document key is absent from the bound manifest.

The preparation summary binds the frontier file bytes and candidate count, and the generic stage commitments include the frontier so mutation, deletion, or injection makes resume fail.

## Exact launch projection and reserve

`project-target-cohort` replays the frozen preparation and authenticated disclosure-clearance commitments before selecting the launch cohort.

For Cycle 1 it requires every resolved-pool `decision_date` to be canonical ISO 8601 and on or after `2026-06-30`.

The command ranks only pre-output acquisition attributes: missing-core-document count, its deterministic estimated cost, and `candidate_id` as the final tie breaker.

Benchmark responses, evaluator scores, labels, and other post-exposure outputs are not ranking inputs.

The first `target_case_count` rows become `target-cohort-selection.jsonl`.

Every remaining completable row is emitted in the same deterministic order as `target-cohort-ranked-reserve.jsonl`, with contiguous reserve and full-frontier ranks, the committed decision date, and the exact missing-document identities, roles, count, and estimated cost used for ranking.

The projection summary commits the order-independent frozen source pool, selected candidate sequence, ranked reserve sequence and bytes, ranking policy, eligibility anchor, budget plan, and every emitted output.

Reordering otherwise identical input records therefore preserves the projection and reserve bytes, while any source-byte change remains visible in the run card's path-bound input commitments.

The reserve does not authorize replacement, purchase, packet construction, freeze, dispatch, or evaluation.

## Compatibility command

`prepare-target-100` remains the exact-100 compatibility command.

It preserves the existing target-100 paths, schemas, stage names, and output shape and does not emit the generic frontier artifact.

## Provider-free legacy materialization

A completed legacy target-100 root does not need to be rerun.

Materialize its full frontier into a separate output root:

```console
uv run legalforecast acquisition materialize-target-cohort-frontier \
  --output-root artifacts/cycle-1/target-100-frontier \
  --preparation-root artifacts/cycle-1/target-100 \
  --preparation-summary artifacts/cycle-1/target-100/target-100-preparation-summary.json \
  --preparation-config artifacts/cycle-1/target-100/target-100-config.json \
  --snapshot-manifest artifacts/cycle-1/snapshots/SNAPSHOT/manifest.json \
  --execute
```

The command verifies the matched legacy schema pair, config self-hash, summary/config binding, every frozen stage-input hash, the exhaustive stage-output tree, selected IDs and aggregate budget frontier, the resolved completed preparation run card, and exact snapshot cycle/batch/hash lineage.

It writes only under the separate `--output-root`, never constructs a provider client, and never mutates the preparation root.

The post-hoc frontier additionally binds the exact legacy preparation summary and success run-card bytes in `source_commitments`.

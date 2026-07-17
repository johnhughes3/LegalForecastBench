# Firecrawl screening implementation commitment v1

`screen-firecrawl-dockets`, `replay-screening-snapshots`, and `promote-terminal-firecrawl-subset` execute a Firecrawl-specific path beyond the five source-neutral files in the global cycle policy.

Every snapshot produced by those commands therefore carries `stage_commitments.firecrawl_screening_implementation` with schema `legalforecast.firecrawl_screening_implementation.v1`.

The commitment contains an exact 21-key `source_sha256` object and `manifest_sha256`, computed over the audited key order as `path`, a NUL byte, the lowercase file SHA-256, and a newline for every key.

The 21 keys are the audited eighteen-file compatibility set plus `legalforecast/ingestion/strict_screen_evidence.py`, `legalforecast/ingestion/screening_snapshot_union.py`, and `legalforecast/ingestion/firecrawl_screening_identity.py` itself.

Whole-file hashing is deliberately conservative: any byte change requires an explicit provider-free migration rather than permitting a silent resume under the old implementation identity.

An absent, extra, missing, malformed, reordered-with-different-content, or digest-mismatched source entry fails closed.

Snapshot resume additionally requires the committed mapping to equal the current implementation exactly.

## Legacy Cycle 1 migration

Artifacts produced at `32057de5942f434697df97b8365ff3f5a176ae47` remain immutable source evidence and are never hand-edited.

Their audited eighteen-file manifest digest is `3e1628b1bbeb3d2af682baaa12815a4c631a64a0ca95eadf2d70e9fa9da419c9`.

`replay-screening-snapshots` is the only compatibility route: it authenticates the pinned assembly, source manifests, screen run cards, normalized success and fetch-exclusion records, and every raw HTML byte commitment; runs the current strict kernel into a fresh store and snapshot; and writes `firecrawl-screening-migration-receipt.json`.

The compatibility route is not open-ended. A source with an implementation commitment records that exact validated commitment as its authority. The single-source terminal history is admissible only when both its complete snapshot-manifest SHA-256 and its screen run-card SHA-256 match the audited Cycle 1 allowlist. The 1,505-candidate historical assembly is admissible only as one indivisible 51-source bundle: its recursive assembly and closure hashes, assembly-card/source/candidate/outcome counts, legacy input aggregate, refresh count, and canonical digest of all 51 manifest/run-card pairs must match the reviewed constants together. No member of that bundle gains independent legacy authority. Missing, contradictory, or unclassified authority fails before target publication.

The receipt records implementation authority separately for every source and records the closed bundle binding when it was used. It reports committed and audited-legacy source counts, includes the historical eighteen-file mapping only when an authenticated legacy source is actually present, records the current implementation commitment and every old and new manifest hash, and reports exact byte-equivalence or an explicit difference for `screened-cases.jsonl` and `exclusions.jsonl`.

The replay command has no provider, PACER, RECAP Fetch, purchase, parser, model, fee-acknowledgment, evaluation, freeze, or dispatch path.

Legacy Firecrawl snapshots are not resumable, union-admissible, target-preparation-admissible, or packet-plannable merely because their old cycle hash still verifies. Union admission recursively validates every source lineage, records the exact recursive Firecrawl source count, and carries the current 21-file implementation commitment whenever that count is nonzero. `plan-public-downloads` checks that lineage before emitting any planner output.

Final planning must consume migrated Firecrawl snapshots and rebuilt unions carrying the v1 implementation commitment.

# Direct CourtListener discovery snapshots

`legalforecast acquisition discover-courtlistener` emits two source-binding outputs in addition to the screened cases, exclusions, raw HTML, and summary: `courtlistener-search-pages.jsonl` preserves every provider page, cursor, term, stable hit identity, and raw hit payload; `courtlistener-raw-artifacts.jsonl` commits every raw docket HTML file by candidate ID, relative path, byte count, and SHA-256.

The completed discovery run card commits all five file outputs, the frozen cycle hash and batch digest, and the noncharging execution state. A discovery run intended for snapshot publication must exhaust every frozen query term. Reaching `--target-clean-cases` or `--max-candidates` is a valid partial discovery result but is not saturated and cannot be materialized.

`legalforecast acquisition materialize-courtlistener-snapshot` is provider-free. It requires an externally pinned `--expected-discovery-run-card-sha256`, verifies the completed run card and every source byte, reconciles the transcript candidate union against exactly one accepted or excluded terminal outcome per candidate, verifies the frozen 2026-06-30 first-written-disposition screening lineage, replays the real page transcript into `CycleAcquisitionStore`, and publishes only when `complete=true` and `saturated=true`. Retrieval failures remain unresolved and block publication. The command never constructs a CourtListener, Case.dev, Firecrawl, PACER, or model client.

An exact completed snapshot may be resumed only when the recomputed `courtlistener_discovery_inputs` commitment matches the immutable manifest. `--no-resume` rejects an existing snapshot. Changed inputs, missing required raw HTML, extra raw files, unsafe paths, identity conflicts, count drift, limit-bound terms, and cycle or batch mismatches fail before publication.

## Cycle expansion after screening-code changes

The cycle identity hashes the screening implementation, including `courtlistener_acquisition.py`. Adding the transcript instrumentation therefore changes the cycle hash. A new direct discovery produced by this implementation must not be appended to an older store or represented as part of the older `b3c74dd...` cycle.

The safe expansion sequence is:

1. Let any already-pinned `b3c74dd...` preparation run finish unchanged.
2. After this implementation is merged, initialize a new cycle root and store with the same 2026-06-30 eligibility anchor and the current screening-source hashes.
3. Provider-free replay the prior complete source assembly under the current screening code into a saturated snapshot in the new cycle.
4. Run a fresh, non-purchasing direct CourtListener discovery in the same new cycle with nonbinding target and candidate limits, and require every term to report `exhausted`.
5. Pin the discovery run-card SHA-256 and materialize the direct discovery snapshot.
6. Run provider-free `union-screening-snapshots` over the old replay snapshot and the new direct snapshot, supplying one ordered `--expected-source-snapshot-manifest-sha256` for each source. The command requires at least two distinct pinned source manifest hashes and batch digests, rejects any non-identical duplicate candidate evidence or raw bytes, copies verified raw bytes into union-owned storage, and emits one synthetic complete saturated union snapshot that remains verifiable after source cleanup.
7. Feed that one union snapshot through `prepare-target-cohort`; downstream batch artifacts can then be combined through the ordinary cycle-acquisition assembly path.

The Firecrawl-specific `replay-screening-snapshots` source format does not consume a direct CourtListener snapshot as an input. The direct snapshot uses the generic verified-snapshot contract accepted by `prepare-target-cohort`; generalizing Firecrawl replay is a separate change.

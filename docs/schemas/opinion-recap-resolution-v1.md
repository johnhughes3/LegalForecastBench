# Opinion lead to RECAP docket resolution v1

`legalforecast batch-002 resolve-opinion-recap-dockets` maps a complete saturated CourtListener opinion-search batch onto numeric RECAP docket identities without PACER, RECAP Fetch, a Case.dev live fetch, or any document purchase.

The resolver uses ordinary noncharging Case.dev docket search first when configured, then authenticated CourtListener `type=r` search with `available_only` omitted as the fallback.

Each provider receives the source case name as one quoted exact phrase under the frozen `quoted_exact_case_name_v1` contract. Embedded quote and backslash syntax is neutralized before quoting; control characters and overlong queries fail closed.

A full Case.dev page without an explicit continuation cursor does not prove exhaustion and is never used to certify a unique match; the resolver falls through to CourtListener's explicit pagination contract.

When Case.dev supplies its `found` total, a cursorless response proves exhaustion only when cumulative returned rows reach that total. Missing continuations with unreturned hits fall through to CourtListener; malformed, changing, or contradictory totals fail closed.

A journaled Case.dev server/provider-availability failure also falls through to CourtListener. Authentication, configuration, malformed-response, and identity errors remain hard failures and never silently consume CourtListener quota.

Every logical request is written to the resolver SQLite journal before dispatch, every terminal lead becomes exactly one `resolved`, `deferred`, or `excluded` journal outcome, and reruns skip terminal leads.

CourtListener's separately metered physical attempts remain governed by the shared durable request-budget ledger.

An operator may explicitly enable the zero-paid Firecrawl contingency for the exact condition where that authenticated ledger cannot reserve another CourtListener REST request. The contingency never activates for authentication, rate-limit, malformed-response, target-response, or Firecrawl provider failures. It performs the same quoted, source-court-constrained `type=r` search against public CourtListener HTML, requires explicit result-count and pagination exhaustion, and accepts identity only through the ordinary strict matcher.

Firecrawl attempts use the basic one-credit proxy under a durable cycle-wide run whose authorization cap cannot exceed 45,000 credits. Every raw HTML page is content-addressed and validated before use; retries are bounded, reservations survive interruption, and provider failures abort retryably without writing a terminal lead outcome. Enabling the contingency requires the source and output batches to use the same cycle store so the shared credit authorization cannot be detached from its frozen source commitment.

The output batch is published only after all frozen source leads reconcile and is marked complete and saturated under one synthetic resolution term.

Only resolved, prior-snapshot-novel RECAP dockets enter that batch; known prior candidates remain auditable `deferred` outcomes and ambiguous or unmatched identities remain auditable `excluded` outcomes.

## Matching contract

The primary match is one unique result with both the same normalized court identifier and normalized docket number.

If no such result exists, the sole permitted fallback is one unique result in the same court whose normalized case name meets the frozen similarity threshold.

Multiple exact matches or multiple qualifying fallback matches fail closed as ambiguity exclusions.

CourtListener fallback pagination must carry explicit `results` and `next` evidence and must exhaust within the frozen per-lead page cap.

## Preserved evidence

Each resolved source hit has numeric `docket_id`, `court_id`, `docket_number`, and `case_name` fields for `seed-direct-search` or `seed-novel-direct-search`, plus `opinion_resolution_evidence` with schema `legalforecast.opinion_recap_resolution.v1`:

- `source_opinion`: source opinion/case-law docket ID, cluster ID, filed date, public URL, metadata-only sub-opinion artifact references, representative provider hit, query term, payload hash, and every contributing source-hit commitment;
- `resolved_recap`: resolved numeric RECAP docket identity;
- `resolver`: provider, exact query, match method, normalized source and resolved identities, and fallback similarity when applicable;
- `ambiguity_proof`: result, distinct-result, same-court, exact-match, and fallback-match counts, matching docket IDs, and exhausted page count;
- `commitments`: source batch/candidate-set commitments, resolver-policy hash, exact provider-response commitment, and selected provider-result commitment.

When multiple opinion leads resolve to one RECAP docket, the lowest numeric source opinion candidate is the deterministic primary and `additional_resolutions` carries each remaining complete resolution-evidence object; no opinion provenance is discarded.

Opinion body text, snippets, and outcome text are never copied into discovery payloads.

The transfer layer includes `opinion_resolution_evidence` in its own source candidate-set commitment and copies it unchanged into the `courtlistener-docket-{resolved_id}` observation lead.

## Rebinding after screening-code changes

An opinion-search or resolved-source batch remains valid discovery evidence when the strict screening implementation changes, but its frozen cycle hash must not be used to describe observations produced by the new code.

`legalforecast batch-002 rebind-direct-search` is the provider-free bridge for that case. It opens the complete saturated source read-only, initializes or verifies the target store against the current screening-source hashes and the explicit eligibility anchor, and transfers the identical committed lead set into a new batch. The target batch and every lead commit the source batch digest, source candidate-set SHA-256, old source cycle hash, and new target cycle hash under `legalforecast.courtlistener_direct_search_cycle_rebind.v1`. The command rejects a same-cycle source, because ordinary same-cycle transfers belong on `seed-direct-search`.

The command has no provider client, never contacts CourtListener, Case.dev, Firecrawl, PACER, or RECAP Fetch, and cannot acknowledge fees or purchase documents.

```bash
uv run legalforecast batch-002 rebind-direct-search \
  --source-store <complete-resolved-source-store.sqlite3> \
  --source-batch-id <complete-resolved-source-batch> \
  --cycle-store <fresh-current-cycle-store.sqlite3> \
  --batch-id <new-current-cycle-rest-screen-batch> \
  --eligibility-anchor 2026-06-30 \
  --summary-output <cycle-rebind-summary.json>
```

`batch-002 observe` re-verifies the target store's frozen screening-source hashes against the running code before constructing a provider client or reserving any request. A stale cycle therefore fails closed before network activity; initialize a current cycle and use the explicit rebind rather than observing in the historical store.

## Live command

```bash
infisical-agent-sandbox run \
  --path /agents/sandbox/legalforecastbench-acquisition \
  -- uv run legalforecast batch-002 resolve-opinion-recap-dockets \
  --source-store <official-cycle-store.sqlite3> \
  --source-batch-id <complete-saturated-opinion-source-batch> \
  --resolver-journal <opinion-recap-resolver.sqlite3> \
  --cycle-store <official-cycle-store.sqlite3> \
  --batch-id <resolved-opinion-recap-source-batch> \
  --prior-snapshot <complete-prior-snapshot-directory> \
  --prior-snapshot-manifest-sha256 <pinned-manifest-sha256> \
  --live \
  --request-ledger <courtlistener-request-ledger.sqlite3> \
  --summary-output <opinion-recap-resolution-summary.json>
```

Repeat the paired prior-snapshot arguments for every frozen prior snapshot.

If Case.dev is unavailable, pass `--courtlistener-only`; this spends CourtListener request capacity for every selected lead but still performs no paid activity.

To authorize the Firecrawl contingency after authenticated CourtListener request-budget exhaustion, add all of the following live-only options:

```bash
  --firecrawl-on-budget-exhaustion \
  --firecrawl-credit-cap <cycle-wide-cap-at-most-45000> \
  --firecrawl-run-id <immutable-run-id> \
  --firecrawl-artifact-dir <durable-raw-html-directory> \
  --firecrawl-max-attempts 3
```

The attempt override is optional and defaults to three. All other Firecrawl options are rejected unless `--firecrawl-on-budget-exhaustion` is present. The command still requires `--live`, an authenticated CourtListener client, and the ordinary durable CourtListener request ledger; offline fixtures cannot activate the contingency.

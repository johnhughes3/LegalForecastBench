# Opinion lead to RECAP docket resolution v1

`legalforecast batch-002 resolve-opinion-recap-dockets` maps a complete saturated CourtListener opinion-search batch onto numeric RECAP docket identities without PACER, RECAP Fetch, a Case.dev live fetch, or any document purchase.

The resolver uses ordinary noncharging Case.dev docket search first when configured, then authenticated CourtListener `type=r` search with `available_only` omitted as the fallback.

Each provider receives the source case name as one quoted exact phrase under the frozen `quoted_exact_case_name_v1` contract. Embedded quote and backslash syntax is neutralized before quoting; control characters and overlong queries fail closed.

A full Case.dev page without an explicit continuation cursor does not prove exhaustion and is never used to certify a unique match; the resolver falls through to CourtListener's explicit pagination contract.

When Case.dev supplies its `found` total, a cursorless response proves exhaustion only when cumulative returned rows reach that total. Missing continuations with unreturned hits fall through to CourtListener; malformed, changing, or contradictory totals fail closed.

A journaled Case.dev server/provider-availability failure also falls through to CourtListener. Authentication, configuration, malformed-response, and identity errors remain hard failures and never silently consume CourtListener quota.

Every logical request is written to the resolver SQLite journal before dispatch, every terminal lead becomes exactly one `resolved`, `deferred`, or `excluded` journal outcome, and reruns skip terminal leads.

CourtListener's separately metered physical attempts remain governed by the shared durable request-budget ledger.

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

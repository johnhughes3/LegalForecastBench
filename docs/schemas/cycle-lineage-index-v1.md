# Cycle Lineage Index v1

`legalforecast.cycle_lineage_index.v1` is machine-local discovery metadata for receipt-backed acquisition cycles.
It is an advisory address book, not provenance or operational authority: every lookup re-authenticates the selected canonical cycle config, immutable receipts, completion cards, and committed outputs through the acquisition coordinator before it reports `VERIFIED`.
The index cannot authorize purchases, evaluation, freeze, dispatch, or publication.

## Fresh-worktree lookup

Keep the index outside Git and expose its location consistently to every worktree:

```bash
export LEGALFORECAST_CYCLE_LINEAGE_INDEX="<absolute-local-state-root>/cycle-lineage-index.json"

uv run legalforecast acquisition locate-cycle-lineage \
  --cycle-id cycle-1-target-100-2026-07-25 \
  --json
```

The JSON result contains no local filesystem paths.
It reports the cycle and current stage, a content-derived root identity, the config and completion-card SHA-256 values, the commit of the code that registered the verified candidate, public-safe artifact commitments, the predecessor config identity, and the state of every configured human-decision stage.
A completed receipted decision is `recorded` and `VERIFIED`; an existing completion card that has not yet been receipted is visible as `recorded_unreceipted` and `UNVERIFIED`, never as current verified authority.

## Register or rebuild

Register a verified lineage after rendering its config and creating its coordinator state:

```bash
uv run legalforecast acquisition register-cycle-lineage \
  --config "<absolute-cycle-config>" \
  --state-root "<absolute-cycle-state-root>" \
  --code-commit "<40-character-verifier-commit>" \
  --json
```

When a new config/root supersedes the current one, add:

```text
--supersedes-config-sha256 <predecessor-config-sha256>
```

Registration is atomic and idempotent.
Deleting an empty or stale local cache loses no authority: rerun `register-cycle-lineage` for each retained config/state pair, in predecessor order, to rebuild it from the authoritative records.
The index deliberately has no separate signature or hash chain because corruption, missing predecessors, cycles, ambiguous active heads, changed configs, unsafe paths, and failed receipt authentication all fail closed during lookup.

Some reviewed Cycle 1 continuations predate coordinator coverage and therefore have completed run cards but no cycle receipt.
Register those without rerunning the stage:

```bash
uv run legalforecast acquisition register-cycle-stage-head \
  --cycle-id cycle-1-target-100-2026-07-25 \
  --command parse-documents \
  --run-card "<absolute-completed-run-card>" \
  --code-commit "<40-character-verifier-commit>" \
  --supersedes-root-identity-sha256 "<registered-predecessor-root-sha256>" \
  --json
```

This path accepts only coordinator-reviewed acquisition commands and executed completion cards, content-authenticates every declared output, and records a content-derived root identity.
It is rechecked on every lookup and never promotes a failed card.
Register a directly executed human-decision card before its successor stage; the locator then carries that verified decision through the explicit supersession chain.

## Closed local schema

The top-level object contains only `schema_version`, `entries`, and `stage_heads`.
Each entry contains the cycle ID, absolute local config and state-root addresses, config SHA-256, verifier code commit, and nullable predecessor config SHA-256.
Each standalone stage head contains its command/stage identity, run-card address and SHA-256, content-derived root identity, verifier commit, and nullable predecessor root identity.
Paths are necessary only to find machine-local evidence and are never emitted by the public-safe status projection.

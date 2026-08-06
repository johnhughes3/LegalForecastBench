# Replacement recovery source producer v1

`legalforecast acquisition build-replacement-recovery-source` is the supported provider-free producer for the closed descriptors consumed by `build-replacement-recovery-index`.

The command derives the source kind, selection, replacement budget, and replacement authority from one completed `recover-recap-fetch-quarantine` run card.

It derives the clearance artifact from the completed clearance run card and, when required, derives the resolved-document artifact from the completed `resolve-post-recovery-documents` run card.

Operators supply evidence locations, not descriptor fields.

The producer replays the purchase policy, cohort binding, current ledger state, recovery output, clearance lineage, resolved-document operation binding, and successor purchase authority before publishing.

It performs no provider, network, paid, evaluation, freeze, or dispatch activity.

For an initial tranche:

```bash
uv run legalforecast acquisition build-replacement-recovery-source \
  --output-root "$RECOVERY_SOURCE_ROOT" \
  --ordinal 0 \
  --recovery-root "$INITIAL_RECOVERY_ROOT" \
  --purchased-clearance-run-card "$INITIAL_CLEARANCE_RUN_CARD" \
  --resolved-post-recovery-run-card "$INITIAL_RESOLVER_RUN_CARD" \
  --purchase-policy "$PURCHASE_POLICY" \
  --cohort-policy "$COHORT_POLICY" \
  --purchase-ledger "$PURCHASE_LEDGER" \
  --initial-controlled-private-root "$INITIAL_PRIVATE_ROOT" \
  --purchase-ledger-initialization-receipt "$LEDGER_INITIALIZATION_RECEIPT" \
  --execute
```

A successor uses a positive `--ordinal` and adds `--replacement-controlled-private-root`.

## Descriptor schemas

An initial descriptor contains exactly:

```json
{
  "kind": "initial_v2",
  "ordinal": 0,
  "purchased_clearance": "/absolute/path/disclosure-clearance.jsonl",
  "purchased_clearance_run_card": "/absolute/path/run-cards/finalize-provenance-quarantine.json",
  "recovery_root": "/absolute/path/recovery",
  "resolved_post_recovery_documents": "/absolute/path/resolved-post-recovery-documents.jsonl",
  "selection": "/absolute/path/target-cohort-selection.jsonl"
}
```

`resolved_post_recovery_documents` is `null` only when the authenticated selection does not require unknown-origin public-resolution lineage.

A successor descriptor contains exactly the initial fields plus:

```json
{
  "replacement_budget_plan": "/absolute/path/replacement-budget-plan.json",
  "replacement_controlled_private_root": "/absolute/path/private-successor-evidence",
  "replacement_purchase_authority": "/absolute/path/replacement-purchase-authority.json"
}
```

Successor ordinals are positive.

The recovery run card must declare `authority_mode=initial_projection` for ordinal zero or `authority_mode=replacement_successor` for a successor.

Extra or missing recovery source commitments fail closed.

The producer captures every file authenticated by the recovery verifier, including the committed terminal-unavailable operation ledger when the recovery contains terminal purchase outcomes.

## Producer run card

The companion run card uses `schema_version=legalforecast.replacement_recovery_source_run_card.v1` and `stage=build-replacement-recovery-source`.

It contains the exact source paths and SHA-256 commitments captured during replay, the current canonical purchase-state digest, the descriptor output commitment, and explicit false provider/paid activity flags.

It contains no wall-clock timestamp, so identical evidence at identical canonical paths produces identical bytes.

Executed publication is immutable.

`--resume` accepts only byte-identical descriptor and run-card outputs; input drift, path rebinding, extra commitments, missing commitments, symlinks, hardlinks, and conflicting pre-existing output bytes are rejected.

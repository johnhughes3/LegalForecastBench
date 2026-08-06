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

When the canonical ledger has advanced through a later authenticated successor, the ordinal-zero producer also accepts the paired `--successor-history-recovery-root` and `--successor-history-controlled-private-root` arguments.

That mode replays the later authority, attempt policy, and recovery; requires the current journal to partition into the authority's exact ordered baseline hashes plus exactly its disjoint approved operation pairs; and verifies the historical initial recovery against the reconstructed baseline snapshot.

The history arguments are rejected for positive ordinals or when supplied singly.

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

New descriptor production requires `schema_version=legalforecast.recap_fetch_quarantine_recovery_run_card.v2`, including its exact terminal-unavailable partition and authorized, recovered, and terminal counts.

The downstream index keeps compatibility with already-existing historical descriptors, but this producer does not mint a descriptor from the legacy six-output `legalforecast.acquisition_run_card.v1` recovery shape.

Extra or missing recovery source commitments fail closed.

The producer captures every file authenticated by the recovery verifier, including the committed terminal-unavailable operation ledger.

That ledger is evidence of provider outcome only; it is not authority to omit selected documents.

When the ledger is nonempty, the resolver and source producer additionally require the complete terminal-disposition bundle: the distinct final disposition selection, screening snapshot manifest, purchase result, and purchase run card.

They replay the existing terminal-purchase disposition verifier against the current purchase journal and require its exhaustive `terminal_failure_pairs` to equal the recovery ledger's exact document-key partition.

The original recovery selection remains unchanged; the distinct disposition selection is used only to authenticate the terminal partition.

The resolver run card commits the terminal ledger path, digest, and record count plus the four disposition-source paths, whose bytes are covered by the ordinary indexed source commitments.

Recovery evidence without this independent disposition authority fails closed and cannot subtract a selected document.

## Producer run card

The companion run card uses `stage=build-replacement-recovery-source`.

Ordinary production uses `schema_version=legalforecast.replacement_recovery_source_run_card.v1`.

Authenticated historical ordinal-zero replay uses the closed `legalforecast.replacement_recovery_source_run_card.v2` schema, which adds `replayed_purchase_state_sha256` for the reconstructed historical prefix.

Both versions contain the exact source paths and SHA-256 commitments captured during replay, the current canonical purchase-state digest in `purchase_state_sha256`, the descriptor output commitment, and explicit false provider/paid activity flags.

The v2 historical digest is distinct from the current digest and never replaces or relabels it.

It contains no wall-clock timestamp, so identical evidence at identical canonical paths produces identical bytes.

Executed publication is immutable.

`--resume` accepts only byte-identical descriptor and run-card outputs; input drift, path rebinding, extra commitments, missing commitments, symlinks, hardlinks, and conflicting pre-existing output bytes are rejected.

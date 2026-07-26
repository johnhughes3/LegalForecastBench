# Case.dev purchase policy v2

`legalforecast.case_dev_purchase_policy.v2` is the sole public derived authority for a new official document-purchase session.
It is produced only from a provider-free, TTY-recorded John Hughes decision over one completed exact `project-target-cohort` projection.
There is no separate public approval artifact and no hand-authored decisions JSON.

The recorder reuses the same full authenticated projection verifier used by cohort materialization.
That verifier replays all nine projection inputs, the authenticated disclosure-clearance run card and review authority, preparation config and summary, snapshot lineage, every one of the eleven projection outputs, and both the semantic projection digest and enriched byte commitments.
Intentional cheapest-target truncation is valid only when that replay proves the exact target is met and the selected and omitted frontier commitments reproduce; authority remains limited to the exact initially selected candidate and document IDs and does not authorize a replacement expansion.

The fee schedule is a separate immutable v1-shaped JSON input containing exactly `source_citation`, `verified_at_utc`, `includes_pacer_fees`, `includes_service_fees`, and `includes_rounding`.
Its source verification time is not the approval time.
The frozen cohort policy supplies the hard cap, per-case cap, purchase rule, and target; the exact projection supplies the document reservation, purchase count, projected obligation, selected IDs, output commitments, and remaining headroom.
No numeric CLI override is accepted.

The canonical ledger namespace must be absent, including its lock and SQLite sidecars, both before and after replay.
The v2 authority therefore binds `opening_committed_spend_usd=0.00`, an empty opening per-case map, and `ledger_initial_state=absent_fresh_initialization_required`; it never assumes that an existing ledger is empty.

Record a decision under a controlled private root outside every packet, public artifact, and freeze tree:

```bash
uv run legalforecast acquisition record-purchase-approval \
  --output-root <absolute-controlled-private-approval-root> \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --target-cohort-root <completed-project-target-cohort-root> \
  --cohort-policy <frozen-cohort-policy.json> \
  --fee-schedule <immutable-fee-schedule.json> \
  --canonical-ledger-path <absolute-new-cycle-purchase-ledger.sqlite3> \
  --execute --no-resume
```

The command requires a real TTY, fixes the reviewer identity to `John Hughes`, obtains UTC time internally, displays all derived facts, accepts exactly `approve`, `reject`, or `free_only`, and requires the complete typed confirmation containing the cycle, request digest, projected cost, one-global-session scope, and free-only fallback.
It writes only `purchase-approval-checkpoint.json` and `run-cards/record-purchase-approval.json` below the controlled root, with mode-safe immutable publication and false provider/PACER/paid-activity fields.
A crash after checkpoint publication is resumed without another prompt or a new timestamp; exact terminal resume is byte-idempotent and incompatible partial metadata fails closed.

Replay it read-only before publication:

```bash
uv run legalforecast acquisition verify-purchase-approval \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --checkpoint <absolute-controlled-private-approval-root/purchase-approval-checkpoint.json> \
  --approval-run-card <absolute-controlled-private-approval-root/run-cards/record-purchase-approval.json> \
  --target-cohort-root <completed-project-target-cohort-root> \
  --cohort-policy <frozen-cohort-policy.json> \
  --fee-schedule <immutable-fee-schedule.json> \
  --canonical-ledger-path <absolute-new-cycle-purchase-ledger.sqlite3>
```

Only `approve` verifies as purchase authority; `reject` and `free_only` remain durable terminal decisions but cannot generate a policy.
The verifier rejects path drift, a copied checkpoint outside the exact controlled root, symlink or hardlink traversal, changed source or output bytes, incomplete run cards, cap/cost/count drift, an existing ledger namespace, and all semantic or byte-commitment mismatches.

Publish the sole public v2 authority once:

```bash
uv run legalforecast acquisition generate-purchase-policy \
  --controlled-private-root <absolute-controlled-private-approval-root> \
  --checkpoint <absolute-controlled-private-approval-root/purchase-approval-checkpoint.json> \
  --approval-run-card <absolute-controlled-private-approval-root/run-cards/record-purchase-approval.json> \
  --target-cohort-root <completed-project-target-cohort-root> \
  --cohort-policy <frozen-cohort-policy.json> \
  --fee-schedule <immutable-fee-schedule.json> \
  --canonical-ledger-path <absolute-new-cycle-purchase-ledger.sqlite3> \
  --output <new-purchase-policy-v2.json>
```

The hash-covered `approval` subtree carries only derived public commitments plus hashes of the private checkpoint and run card; it does not expose a private path.
Duplicate v2 publication is rejected, even for identical bytes.
Recording, verification, and policy generation perform no provider request, PACER fee acknowledgment, purchase, evaluation, freeze, or dispatch.

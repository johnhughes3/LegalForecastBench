# Document-repair purchase issuance

**Status:** adopted 2026-08-17 · closes the issuance half of `legalforecastbench-3ak.24`.

The document-repair executor has always enforced paid access fail-closed. Until this note there was no supported tool that *issued* what it enforces, so an owner-authorized tranche could not execute even with authorization in hand.

## What the executor demands

| Enforcement | Demands |
| --- | --- |
| `build_document_repair_purchase_authority` | a replay-minted `DocumentRepairExecution` **and** an independently approved `legalforecast.case_dev_purchase_policy.v2` artifact, while the canonical ledger is still **absent** |
| `verify_document_repair_purchase_runtime` | that policy's canonical ledger **initialized**, with a receipt authenticating against the policy and cohort file digests |

Neither contract changes here. The issuance path builds to them.

## Operator flow

Three commands, then one execution. All of it is provider-free until the execution step.

```
# 1. Prepare — show the projection, record nothing. Repeat freely.
legalforecast acquisition record-document-repair-purchase-approval \
  --repair-execution-root      <tranche root> \
  --repair-manifest            <root>/repair-manifest.jsonl \
  --repair-plan-approval       <root>/repair-plan-approval.json \
  --docket-snapshot-manifest   <root>/docket-snapshot-manifest.json \
  --source-lineage             <root>/source-lineage.json \
  --source-lineage-sha256      <external pin> \
  --docket-snapshot-dir        <root>/docket-snapshots \
  --cohort-policy              <cohort policy> \
  --fee-schedule               <fee schedule> \
  --canonical-ledger-path      <ledger that must not yet exist> \
  --controlled-private-root    <private root>

# 2. John confirms at the TTY — add --execute to the same command.

# 3. Publish the approved v2 policy from the private evidence.
legalforecast acquisition verify-document-repair-purchase-approval \
  ... same source flags ... \
  --checkpoint              <private root>/purchase-approval-checkpoint.json \
  --approval-run-card       <private root>/run-cards/record-purchase-approval.json \
  --purchase-policy-output  <root>/approved-purchase-policy.json

# 4. Prove the binding. Consumes nothing; run it as often as you like.
legalforecast acquisition verify-document-repair-purchase-policy \
  ... same source flags ... \
  --purchase-policy <root>/approved-purchase-policy.json
```

Then, and only in the paid execution process, `initialize_document_repair_purchase_runtime` mints authority, initializes the ledger, and verifies the runtime, and `run_document_repair_execution` runs the tranche.

## The displayed string is the only signing material

Every figure the recorder shows — cost, document count, case count, per-document reservation, ceiling, headroom, ledger path, execution digest — is derived from bytes the recorder itself read and digested. It mints the `DocumentRepairExecution` in-process, so no operator-supplied number reaches the signed phrase, and it refuses any projection the executor would later reject rather than letting an unexecutable one reach the screen.

A confirmation phrase circulated in chat is **not** authoritative and cannot be made authoritative by pasting it back. The confirmation is matched byte-for-byte: leading or trailing whitespace, a wrapped newline, or a case change is a refusal, not a near-miss.

The tranche root supplies its own source lineage, which pins a cohort-policy digest. That digest must equal the digest of the cohort policy file supplied separately on the command line, so a tranche root cannot certify itself against a policy nobody read.

## Why no command initializes the ledger

Authority can be minted only while the canonical ledger is **absent**; the runtime verifier requires it **present**. Neither the authority nor the runtime object can be serialized and rebuilt, so both must be created in the process that executes.

A separate initialization step therefore closes the window permanently: once the ledger exists, no later process can mint authority for that policy, and the tranche cannot execute at all. That is why initialization is exposed only as `initialize_document_repair_purchase_runtime`, which performs authority, initialization, and runtime verification in the one workable order. `tests/test_document_repair_purchase_approval.py::test_initializing_the_ledger_before_authority_is_unrecoverable` holds that behavior in place.

Corollary for scheduling: the TTY sitting and the paid execution are separate events, and the ledger path recorded at the sitting must still be absent when execution starts.

## Resuming an interrupted execution

An execution that dies partway leaves a ledger holding confirmed rows for what it bought and `planned` rows for what it did not. That ledger is the record of the spend, so it must not be deleted — deleting it restores authority mintability, which is the double-charge path. `acquisition resume-document-repair-purchase` continues from it instead.

```bash
legalforecast acquisition resume-document-repair-purchase \
  <the same tranche source arguments the sitting used> \
  --controlled-private-root "$PRIVATE_ROOT" \
  --checkpoint "$PRIVATE_ROOT/purchase-approval-checkpoint.json" \
  --approval-run-card "$PRIVATE_ROOT/run-cards/record-purchase-approval.json" \
  --purchase-policy "$ROOT/approved-purchase-policy.json" \
  --acquired-dir "$ROOT/acquired" \
  --expected-request-sha256 "$REQUEST_SHA256" \
  --expected-execution-sha256 "$EXECUTION_SHA256"
```

That is the **preflight**, and it is the default. It replays the recorded approval in full, requires the published policy to reproduce byte for byte from that verified approval, re-proves the already-acquired documents against the digests the interrupted run recorded, reads the ledger through the read-only snapshot path, and prints the plan. It changes no filesystem state and needs no provider credential.

Dispatching needs `--execute`, `--request-ledger` (reuse the tranche's existing request-budget database), and two pins that must come from the interrupted run's **halt record**: `--expected-purchase-state-sha256` and `--expected-confirmed-document-ids`.

Those two exist because the initialization receipt testifies only to the ledger's *initial* state. A ledger restored from an older copy of the same lineage, or edited to put a spent row back to `planned`, satisfies every other check while offering an already-bought document as buyable. The digest is compared while the process holds the ledger write lock, before anything is written; the document-id set is the same claim in a form a human can check line by line against the halt record, which a digest is not.

Take both from evidence recorded when the run halted — **never** from a preflight of the ledger you are about to act on. A value read out of the artifact it authenticates cannot detect a rollback of that artifact, which is why the preflight deliberately does not print a ready-to-paste `--execute` line: it reports what the ledger reads *now*, for you to compare against the record.

What a resume will and will not touch, by journal status:

| status | action |
| --- | --- |
| `planned` | dispatched |
| `confirmed` | carried forward from the bytes already on disk; no provider call |
| `submitted`, `queued`, `unknown`, `failed` | refuses; recover the outcome by broker receipt or provider status first |

Ordering, stop-on-unknown, receipt minting and the approved ceiling stay with `run_document_repair_execution`; the resume adds only the status partition and the carry-forward. The `--expected-*` pins are supplied on the command line rather than read from the tranche for the same reason `--source-lineage-sha256` is: a commitment read from the material it commits to proves nothing.

Two limits worth knowing. A transport blip on the *free* verification GET that precedes each submission aborts the run before any charge, leaving the row `planned` — the command is re-runnable by construction. And the carried-forward documents are proved from the interrupted run's own unsigned progress log plus a re-hash of each file, so the acquired directory and its log are trusted as one unit; that check catches corruption and mismatch, not an actor able to rewrite both consistently.

## Frozen-field mapping

The public approval body is fixed by `_validated_public_purchase_approval`, which admits *exactly* the project-target-cohort field names. A repair tranche therefore reuses those names, and its own lineage lives in `output_commitments`, the one free-form member:

| Frozen field | Document-repair meaning |
| --- | --- |
| `target_cohort_root` | repair tranche root holding every input |
| `target_cohort_run_card_sha256` | approved repair-plan approval record |
| `projection_sha256` | `execution.execution_sha256` |
| `selection_sha256` | `execution.full_plan_sha256` |
| `budget_plan_sha256` | canonical repair purchase-budget record |
| `target_case_count` / `selected_case_count` | paid cases in the tranche |
| `rule` | `buy_exact_approved_document_repairs` |

`output_commitments` additionally carries `repair_execution` (which the executor requires), `repair_full_plan`, `repair_manifest`, `repair_plan_approval`, `repair_purchase_budget`, `docket_snapshot_manifest`, `source_lineage`, and `cohort_policy`.

Private evidence reuses the established `legalforecast.purchase_approval_checkpoint.v1` recorder rather than forking a second immutable-write spine, so this path introduces no new schema identifier. Cross-feeding is safe in both directions: each verifier recomputes its own request from its own inputs and compares the whole record, so a cohort checkpoint fails closed here and a repair checkpoint fails closed in the cohort recorder.

Per-document reservation is the contract's own `USD 3.00`; projections are `3.00 × document count`. Any tranche total circulated elsewhere is an estimate, not the projection — read the recorder's output.

## Historical exception: the 147-document tranche (recorded 2026-08-17)

The 147-document repair tranche executed under a **substantively authorized but mechanically unsupported** checkpoint, before this issuance path existed.

- **What happened.** A private script (`document-repair-full-gate2a/mint_paid_policy.py`) hand-synthesized the checkpoint and run card from a confirmation string pasted into chat, and assembled the v2 policy body directly. Its own checkpoint records `typed_confirmation_normalized_from_wrapped_chat: true`.
- **Artifact reference.** Gap analysis recorded at SHA-256 `45401f5e2b72179a77df2611acbf4e9b141b74c5d27c1c63f25604afa3b5d369`, in the gate2a private tree under `needs-human-adjudication/s2b-repair-purchase-issuance-gap-2026-08-17.json`.
- **Why the spend itself was sound.** The owner did approve this exact tranche; the policy's hashes bound the real execution, selection, and document set; the projected cost respected both the per-case and cycle ceilings; and the executor's own authority and runtime checks passed against those bound hashes. The defect is in the *mechanism* that produced the checkpoint, not in the authorization or the amount.
- **Why it is still a defect.** A chat-normalized string means the reviewer signed material derived somewhere other than the recorder, so the TTY requirement proved nothing about what was on screen at the moment of signing. Repeating it would satisfy every enforcement check while defeating the property those checks exist to protect.
- **Disposition.** Not unwound. `legalforecastbench-3ak.24` closes the mechanism gap; every tranche from 2026-08-17 forward issues through the commands above. The private script is precedent for nothing.

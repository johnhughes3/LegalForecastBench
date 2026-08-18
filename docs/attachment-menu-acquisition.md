# Attachment-menu acquisition

Operator flow for making attachment-level documents purchasable at all.

## Why this exists

An attachment-level memorandum cannot be purchased while CourtListener holds no `RECAPDocument` row for it, and that row appears only once CourtListener has parsed the entry's PACER attachment menu. Where the menu was never ingested, no authenticated `source_document_id` exists anywhere in the world, so no purchase projection can be built — the seven paid attachment rows on `legalforecastbench-3ak.20` sat in exactly that state through 65 free refreshes and an independent second-endpoint check.

Fetching the menu is what creates the rows. It costs PACER money, so it runs through the same shape as every other charge in this repository: an authenticated plan, an owner decision bound to that plan's digest, then an executor that will not exceed what was signed.

## The three commands, in order

Everything before `fetch-attachment-pages` is free and contacts no PACER endpoint.

### 1. Plan — free, authenticated

```bash
uv run legalforecast acquisition plan-attachment-pages \
  --plan-id <bare-token-naming-this-plan> \
  --entry <candidate-id>:<entry-number> \
  --entry <candidate-id>:<entry-number> \
  --per-menu-ceiling-usd 0.20 \
  --output <plan.json>
```

Each requested entry is read live from CourtListener rather than copied from a prior artifact, so the plan's digest binds what CourtListener holds right now. Every requested entry lands in exactly one of two lists:

- **targets** — no attachment row exists, so the menu must be fetched.
- **skipped** — nothing to buy: the menu is already ingested (`already_ingested`), the entry has no single main document (`main_document_not_exact`), or the main document carries no `pacer_doc_id` (`main_document_has_no_pacer_identity`).

If nothing needs a paid menu, the command refuses rather than emitting a plan that would charge for data already held.

On the ceiling: PACER bills attachment menus **per page**, so a long attachment list can exceed one page's charge. Set `--per-menu-ceiling-usd` above the single-page rate unless you know every menu is short.

### 2. Authorize — free, and only John can do it

```bash
uv run legalforecast acquisition authorize-attachment-pages \
  --plan <plan.json> \
  --output <authorization.json>
```

This prints the loaded plan — digest, menu count, ceiling, every target entry, and every exclusion with its reason — and waits for one typed line at the terminal.

Run it **bare in a terminal**. It needs no credentials and no sandbox launcher, and wrapping it in one can swallow the TTY — the command would then refuse a legitimate approval, which reads like a structural halt when it is only a plumbing mistake.

**The confirmation is derived from the plan this command loaded.** Do not carry a confirmation string in from a bead comment, a projection artifact, or a chat message: those bind a digest that may have moved, and typing a stale hash into a fail-closed prompt burns an authorization window instead of stopping safely. Read the line off the screen.

The command refuses a piped or file-supplied confirmation. A confirmation that is not a person reading a number at a terminal is not owner authorization.

**The authorization is single-use.** The first fetch that dispatches a charge marks it consumed, and it will not authorize a second run. That is deliberate: after a run that spent money, the correct next step is a fresh owner decision, not a rerun of the same file.

### 3. Fetch — charge-bearing

```bash
uv run legalforecast acquisition fetch-attachment-pages \
  --plan <plan.json> \
  --authorization <authorization.json> \
  --request-ledger <request-budget.sqlite3> \
  --dispatch-journal <dispatch-journal.sqlite3> \
  --output <receipt.json> \
  --execute
```

Requires `COURTLISTENER_API_TOKEN`, `PACER_USERNAME`, and `PACER_PASSWORD`; run it under the acquisition sandbox launcher so those come from Infisical rather than the host environment.

**Pass the same `--dispatch-journal` path on every run of a plan.** It is the durable record of what was charged, and it is what stops an entry whose fetch failed from being charged again. A fresh journal path is a fresh keyspace, which is the one way to defeat the guard.

`--output` must not already exist. The command reserves it before spending, so a rerun against a used receipt name refuses without charging.

What it guarantees:

- Only menus the signed plan names, **exactly once each**. A dispatched charge is never retried — a failed menu is a recorded outcome that needs fresh authorization.
- An authorization that does not bind this exact plan is refused **before** any credential is read or ledger created.
- Each intended charge is written to the dispatch journal **before** the POST that incurs it, so a crash cannot leave money spent with nothing on disk to say so.
- A menu ingested by someone else between signing and dispatch is skipped without charge.
- A fetch that completes but creates no attachment rows is recorded as **failed**, not success. CourtListener's documentation says attachment pages are fetched "same as PDFs, but with `request_type` set to `3`", and the observable evidence agrees, but the executor verifies per row rather than trusting it.
- A dispatch with no durable disposition halts the run; later targets are recorded `not_attempted` rather than charged into an unknown state.

Exit code is `1` when the run halted, `0` when every target settled, `2` on a usage error, and `3` on a refusal. **Exit `3` always means nothing was charged.** Once a charge can go out the command reports a halt instead, names the journal path, and states how many dispatches it holds.

### Resuming after a failed or interrupted run

1. Read the dispatch journal, not just the receipt — it is authoritative about what was charged.
2. Sign a **fresh** authorization against the same plan (the previous one is consumed).
3. Re-run with the **same** `--dispatch-journal` and a **new** `--output`.

Entries already dispatched come back as `already_dispatched` with `charge_dispatched: false`; only entries that never reached the wire are charged. To deliberately re-charge an entry whose menu genuinely never arrived, build a new plan: a new digest is a new keyspace and a new owner decision, which is the intended cost of a second charge.

## Reading the receipt

Per-row `disposition` is one of `fetched`, `already_ingested`, `already_dispatched`, `failed`, `unknown`, or `not_attempted`. `charge_dispatched` is the honest spend signal — `unknown` rows may have been billed. `already_dispatched` means an earlier run under this plan already charged for that entry, so this run did not.

`ceiling_upper_bound_usd` is exactly that: the authorized per-menu ceiling times the number of charge-bearing dispatches. The RECAP Fetch API does not report the PACER charge, so this is never a claim about the actual invoice.

## What comes next

Fetched menus create the attachment rows, which makes selector resolution a free GET. Re-run the selector refresh, then build the document purchase projection against the now-authenticated `source_document_id` values. Buying the attachment documents themselves is a separate authorization on the existing `request_type=2` purchase path — this flow only makes them nameable.

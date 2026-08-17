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

### 3. Fetch — charge-bearing

```bash
uv run legalforecast acquisition fetch-attachment-pages \
  --plan <plan.json> \
  --authorization <authorization.json> \
  --request-ledger <request-budget.sqlite3> \
  --output <receipt.json> \
  --execute
```

Requires `COURTLISTENER_API_TOKEN`, `PACER_USERNAME`, and `PACER_PASSWORD`; run it under the acquisition sandbox launcher so those come from Infisical rather than the host environment.

What it guarantees:

- Only menus the signed plan names, **exactly once each**. A dispatched charge is never retried — a failed menu is a recorded outcome that needs fresh authorization.
- An authorization that does not bind this exact plan is refused **before** any credential is read or ledger created.
- A menu ingested by someone else between signing and dispatch is skipped without charge.
- A fetch that completes but creates no attachment rows is recorded as **failed**, not success. CourtListener's documentation says attachment pages are fetched "same as PDFs, but with `request_type` set to `3`", and the observable evidence agrees, but the executor verifies per row rather than trusting it.
- A dispatch with no durable disposition halts the run; later targets are recorded `not_attempted` rather than charged into an unknown state.

Exit code is `1` when the run halted, `0` when every target settled.

## Reading the receipt

Per-row `disposition` is one of `fetched`, `already_ingested`, `failed`, `unknown`, or `not_attempted`. `charge_dispatched` is the honest spend signal — `unknown` rows may have been billed.

`ceiling_upper_bound_usd` is exactly that: the authorized per-menu ceiling times the number of charge-bearing dispatches. The RECAP Fetch API does not report the PACER charge, so this is never a claim about the actual invoice.

## What comes next

Fetched menus create the attachment rows, which makes selector resolution a free GET. Re-run the selector refresh, then build the document purchase projection against the now-authenticated `source_document_id` values. Buying the attachment documents themselves is a separate authorization on the existing `request_type=2` purchase path — this flow only makes them nameable.

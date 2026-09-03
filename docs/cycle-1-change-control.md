# Cycle 1 Change Control

> **Status (2026-09-03).** Mostly retired. The cadence rules below — one active gate-changing integration lane, focused-before-full test ordering, batched remediation, and the correctness/security emergency path — are the only part still in force, and they now apply to ordinary work in this repository rather than to a legacy chain. The **frozen authenticated-byte regime is superseded** by the 2026-08-30 replan: Cycle 1 finishes through the new corpus factory, which carries one locked run manifest and no per-document digests. The Cycle 1 chain those byte contracts governed left this repository in #1034 and now lives in the companion private corpus repository, so the "Frozen byte contracts" section below describes artifacts this package no longer produces. This document's terminal gate `LegalForecastBench-5qd6.41` was cancelled on 2026-08-30. The governing standard is now the Standard of Rigor in [AGENTS.md](/.agents/AGENTS.md).

**Status:** adopted 2026-08-07 · applies through the final Cycle 1 gate `LegalForecastBench-5qd6.41` (freeze + sharded official dispatch + fan-in/publish).

This note is change control for the remainder of Cycle 1 — not a correctness freeze and not a governance framework. It exists to stop a measured failure pattern: passing full suites discarded because the candidate head kept moving, and gate-hardening changes replenishing the defect stock.

## Frozen byte contracts

The authenticated byte contracts and required schema semantics already in the live Cycle 1 chain are frozen:

- **Artifact canonical JSON codec** — `legalforecast.ingestion.canonical_json` (`canonical_json_bytes` / `canonical_json_value_bytes`): key-sorted, compact separators, UTF-8 (`ensure_ascii=False`), `allow_nan=False`, trailing newline on artifact bytes.
- **Manifest/freeze codec** — `legalforecast.protocol.manifest.canonical_json` and `hash_payload` (key-sorted, compact separators, ASCII-escaped, `default=str`, SHA-256), producing `legalforecast-mtd-manifest-v1` manifests.
- **Commitment digest form** — lowercase SHA-256 hex, `sha256:`-prefixed where the schema requires it (`legalforecast._hashing`).
- **Run cards** — `legalforecast.acquisition_run_card.v1` required-field semantics.
- **Versioned artifact schemas** — every `legalforecast.*.v<N>` schema id already emitted or validated in the live Cycle 1 chain, as documented in `docs/schemas/`.

New observational metadata goes in non-authoritative sidecars during Cycle 1. Optional fields must not be added to whole-card authenticated bytes, even when backward-compatible.

## Working cadence

- **One active gate-changing integration lane.** At most one branch/PR at a time may change gate behavior (validators, byte contracts, preflight gates, schema semantics). Independent non-contract work may run in parallel.
- **Review-stable head.** A candidate head is review-stable when review findings are resolved and no further gate-changing commits are queued behind it. Full-suite validation targets review-stable heads only.
- **Focused before full.** While review is moving, run focused tests on the touched area; run one full suite after the candidate head is review-stable, not per iteration.
- **Batched remediation.** Run collect-all-violations preflights once, then fix every finding from that run in one fix cycle — no fix-one-rerun-fix-one loops.

## Emergency path (correctness/security only)

A security or provenance correctness defect may change a frozen contract only through an explicit, versioned emergency migration that (a) states the affected artifacts, (b) validates the complete current chain, and (c) batches all known violations into that one migration. No force flag, no failed-card promotion, no hash patch. This note does not authorize provider calls, purchases, freeze, dispatch, or publication.

## Velocity counters (computed at the next retrospective)

All four are derived from existing artifacts (run cards, stage roots, decision ledgers, session transcripts) with no new collection infrastructure; if a counter turns out to need new infrastructure, drop that counter. They are computed once at the next retrospective, not continuously.

1. **Fail-closed catch point** — fail-closed rejections caught pre-merge ÷ all fail-closed rejections (pre-merge + production runs).
2. **Stage-root economy** — stage roots created ÷ conceptual pipeline steps executed.
3. **Decision-to-action latency** — elapsed time from a human decision being durably recorded to the first action on it, per recorded decision.
4. **Idle gaps** — count of idle gaps over 30 minutes ÷ working sessions.

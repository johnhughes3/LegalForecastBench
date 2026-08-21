# Replacement recovery consolidation run card v3

Schema identifier: `legalforecast.replacement_recovery_consolidation_run_card.v3`.

This Cycle 1 migration leaves the frozen v1 and v2 cards unchanged. It admits exactly one new mode: an authenticated `legalforecast.exact100_successor_replacement_state.v3` target whose paid-document authority is the union of the canonical purchase ledger and the one owner-ratified external billing register pinned by the implementation.

A v3 card is a completed provider-free consolidation with `target_projection_mode: "exact100_successor_replacement_v3"`. Its first ten `input_paths` have fixed meanings: tranche index, tranche-index run card, authenticated selection, authenticated v3 target root, purchase policy, cohort policy, canonical purchase ledger, controlled private root, ledger-initialization receipt, and external billing register. Tranche inputs follow slot 9. The register is mandatory, must authenticate as the pinned exact bytes, must not overlap canonical-ledger operations, and authorizes only the recorded candidate/document identities at their recorded document SHA-256 values.

The verifier replays the v3 target, register, recovery tranches, and complete output bytes; requires the reproduced input path sequence and source commitments to equal the card; and carries the register's per-document commitments through the verifier-issued materializer capability. Legacy purchased-manifest mode, a v2 target with a register, and a v3 target without the register are invalid rather than alternative v3 encodings.

The schema does not authorize retrieval, purchase, provider, evaluation, freeze, or dispatch activity.

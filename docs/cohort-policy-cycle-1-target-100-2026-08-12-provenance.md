# Cycle 1 exact-100 document-selection repair policy provenance

This note records the authority and derivation for
`cohort-policy-cycle-1-target-100-2026-08-12-decisions.json`. It is not a
policy artifact and is never consumed as runtime authority.

## Human authority

- Epic `legalforecastbench-3ak` records John's 2026-08-12 decision to repair
  the invalidated exact-100 document selection through a versioned successor
  lineage rather than mutate frozen artifacts.
- Task `legalforecastbench-3ak.3` records the authorized policy changes:
  require filed oppositions and replies, expand the claim-bearing pleading
  vocabulary, and require validation that selected bytes match their asserted
  document role.
- The repair protocol also requires filed surreplies and court-ordered
  supplemental briefing tied to the target motion. These roles make the
  briefing requirement complete without using decision outcomes to select
  documents.

## Preserved values

All non-packet-completeness values are copied from the frozen 2026-07-25
exact-100 decisions. In particular, the acquisition hash, eligibility and
search windows, target-motion selector, budget caps, disclosure rules,
reason-code transition semantics, reduced-N tiers, and prediction-unit floor
are unchanged.

The unique cycle identifier is
`cycle-1-target-100-2026-08-12-document-selection-repair`. Current reason-code
lists are mechanically supplied by `generate-cohort-policy` from the
cycle-store taxonomy.

## Commitments

The decisions input has SHA-256
`7f5fcefb4ec862ba7477dcb201c5383354fd3d17e2641cda3bbe04af6ed85eaa`.
The generated policy has internal identity
`e1606aae7d8d9956267b09bb26fc1211874ebe4705e6fc65402a775f70bed848`
and complete-file SHA-256
`767c0e353d17eb24bc7ad8fdc1649062bc7f15e45053bd6a205345f8bf300382`.

# Cycle 1 exact-100 document-selection policy v3 provenance

This note records the authority and derivation for
`cohort-policy-cycle-1-target-100-2026-08-13-decisions.json`. It is
non-authoritative and is not consumed by the policy validator.

## Human authority and rationale

Bead `legalforecastbench-3ak.3` requires a versioned successor to the frozen
2026-07-25 policy. The successor closes four selection-accounting gaps:

- all filed oppositions, responses, replies, surreplies, and court-ordered
  supplemental briefs tied to the target motion are required;
- the attacked claim-bearing pleading, including non-complaint claim filings,
  and any prior operative pleading needed to understand status are required;
- selected bytes must be validated against their asserted role; and
- every unselected pleading- or briefing-like entry requires a recorded
  exclusion reason.

Candidate `70754103` established both generic response/reply omission and the
risk of summons bytes occupying an amended-complaint slot. Candidate
`71212565` established that a target motion can attack a crossclaim and require
an originating interpleader claim-bearing filing rather than a complaint of
record.

The committed v2 artifact remains immutable. V3 supersedes it because v2 did
not encode the response role, prior-operative-pleading rule, fallback
claim-bearing role, or exclusion ledger.

## Preserved values

The v3 decisions are byte-for-byte value-equivalent to the frozen 2026-07-25
decisions after removing `packet_completeness` from both objects. This preserves
the cycle identifier, acquisition hash, eligibility and search windows,
single-target-motion selector, cost ranking and caps, disclosure and
replacement rules, reason-code transition semantics, and reduced-N policy.

## Commitments

The decisions input has SHA-256
`5031995435b17d70c16fea20cd895cb216ac2d57366708405afddd0ff321493b`.
The generated policy has internal identity
`d9bb6b40bf4914ed94e17b66b5ba2cfd2a0051dbb8dc1947269fe65886806216`
and complete-file SHA-256
`c152ec59229cd46e37819f0656fd1b8ef5e9ffee05678a109f0b9547fb96e7de`.

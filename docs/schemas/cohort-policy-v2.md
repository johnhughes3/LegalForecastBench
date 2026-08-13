# Cohort policy v2

`legalforecast.cohort_policy.v2` is the versioned successor to the frozen
`legalforecast.cohort_policy.v1` contract. It preserves every v1 acquisition,
selection, spending, disclosure, and reduced-N rule while replacing only
`packet_completeness`.

The v2 `packet_completeness` object contains exactly:

- `motion_or_combined_memorandum_required`: must be `true`.
- `required_briefing_roles_if_docketed`: must contain, in order, `opposition`,
  `reply`, `surreply`, and `court_ordered_supplemental_brief`. Each role is
  required only when filed before the decision and tied to the target motion.
- `attacked_claim_bearing_pleading_required`: must be `true`.
- `required_claim_bearing_pleading_roles`: must contain, in order, `complaint`,
  `amended_complaint`, `counterclaim`, `crossclaim`,
  `third_party_complaint`, and `interpleader_complaint`. The packet must
  include the claim-bearing pleading actually attacked by the target motion;
  the list is a closed recognition vocabulary, not a requirement to find every
  role in every case.
- `document_role_bytes_validation_required`: must be `true`; a docket label
  alone cannot establish that the selected bytes perform the asserted role.

Unknown, missing, reordered, or duplicate roles fail validation. The generator
infers v2 only from the v2 packet-completeness fields, so unchanged v1 decision
inputs continue to produce byte-identical v1 artifacts. Verification dispatches
on the artifact's explicit schema version and never reinterprets frozen v1
bytes as v2.

Like v1, the top-level artifact contains exactly `schema_version`, `policy`,
and `policy_sha256`. The canonical JSON and policy-hash rules are unchanged.
This successor does not rewrite any prior policy or observation manifest.

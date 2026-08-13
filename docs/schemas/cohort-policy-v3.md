# Cohort policy v3

`legalforecast.cohort_policy.v3` supersedes v2 without changing or
reinterpreting any v1 or v2 artifact. It preserves the frozen 2026-07-25
policy values outside `packet_completeness`.

The v3 `packet_completeness` object contains exactly:

- `motion_or_combined_memorandum_required`: `true`.
- `required_briefing_roles_if_filed`: the ordered closed vocabulary
  `opposition`, `response`, `reply`, `surreply`, and
  `court_ordered_supplemental_brief`. Every filed predecision item tied to the
  target motion is required; recognition does not depend on a docket label.
- `attacked_claim_bearing_pleading_required`: `true`. Selection follows the
  pleading the target motion actually attacks, not a generic complaint slot.
- `required_claim_bearing_pleading_roles`: the ordered recognition vocabulary
  `complaint`, `amended_complaint`, `counterclaim`, `crossclaim`,
  `third_party_complaint`, `interpleader_complaint`, and
  `other_claim_bearing_filing`.
- `prior_operative_pleadings_required_when_necessary_to_understand_status`:
  `true`. A superseded or originating pleading is required when needed to
  explain why the attacked pleading is operative or how its claims arose.
- `document_role_bytes_validation_required`: `true`. Content, not the docket
  label alone, must validate every required role before admission.
- `unselected_pleading_or_briefing_entries_require_exclusion_reason`: `true`.
  Every pleading- or briefing-like docket entry not selected must appear in an
  exclusion ledger with a reason; silent omission violates the policy.

Unknown, missing, reordered, duplicated, or false requirements fail
validation. Generation infers v3 from its unique packet fields. Verification
dispatches on the artifact's explicit schema version, so frozen v1 and v2
bytes retain their original semantics.

The top-level artifact and canonical commitment rules are unchanged:
`schema_version`, `policy`, and `policy_sha256`.

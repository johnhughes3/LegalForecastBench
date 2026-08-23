# Manifest unitizer r2 authority v1

`legalforecast.cycle1.manifest_unitizer_r2_authority.v1` is the immutable sidecar for the disjoint `stage51-r2-proposal-v1` mode of `legalforecast acquisition llm-unitize-manifest`.

It does not reinterpret or replace `legalforecast.cycle1.stage51_finalized_units_integration.v1`. The historical `finalized-v1` command path and its run-card behavior remain unchanged.

The r2 mode promotes only one exact, owner-approved Stage 5.1 proposal after independently revalidating its selection, overlay, canonical packet, validation report, semantic diff, byte inventory, checksum manifest, integration proposal, and approval observation. The approval observation is hash-pinned evidence that the exact lines were observed in the durable reference; it is explicitly not a cryptographic authentication of Beads authorship or human identity.

The sidecar records:

- the authority mode, exact owner reference, packet approval line, spend approval line, and approval-observation byte commitment;
- every proposal, inventory, and fresh-five input commitment used to authenticate the r2 path;
- the exact corrected-selection order and its `94 retained + 1 reprocessed + 5 provider-free reconstructed` partition;
- the current model-visible PDF and Markdown byte commitments used for source and citation validation;
- one query-only journal-reconstruction commitment per fresh candidate, including the prompt, raw output, normalized response, provider response, accounting, and historical attempt ordinal commitments;
- hashes and byte counts for the primary outputs, metadata, and log written before the ordinary run card; and
- explicit false values for provider calls, new paid activity, paid activity requested/executed, and journal mutation.

The fresh-five reconstruction opens a read-only canonical journal snapshot, validates the raw provider response and accounting, reconstructs through the current Stage A code, and compares the stable audit fields and exact unit rows with the pinned five-row evidence. It never inserts a provider attempt, creates an authority ordinal, opens a provider client, or mutates the journal.

R2 publication is create-only. Output paths must be distinct, must not alias authenticated inputs, and must not exist before publication. The command rechecks its authenticated proposal and current manifest inputs immediately before writing. It writes primary outputs first, then immutable metadata, log, and authority sidecar, and writes the unchanged-field-set `legalforecast.acquisition_run_card.v1` last as the completion marker. A partial directory without that run card is not a completed issuance.

The executed output must contain exactly 100 unique candidates in corrected-selection order and exactly 425 scorable prediction units. A dry run performs the same provider-free authentication but marks the sidecar non-authoritative and all paid-activity fields false.

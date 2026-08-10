# Exact-100 successor replacement v2

`legalforecast.exact100_successor_replacement_config.v2`, `legalforecast.exact100_successor_replacement_state.v2`, and `legalforecast.exact100_successor_promotion.v2` extend the provider-free exact-100 successor contract to a wider authenticated candidate horizon. They do not reinterpret the v1 schemas, change any v1 bytes, mutate the predecessor cohort, or create a caller-selectable replacement route.

The v2 projector starts from the replay-verified v1 exact-100 predecessor and removes only the candidate established by the sealed target-document eligibility audit as the sole `stipulated_ineligible` terminal exclusion. It then derives the complete nonselected candidate horizon from the authenticated screened universe and its successor-exclusion ledger. The replacement is the first candidate that passes the unchanged ranking and eligibility rules after applying only replay-verified [semantic repair v1](exact100-successor-semantic-repair-v1.md) records.

The caller cannot provide a candidate ID, rank, repaired role, document list, or alternate ranking rule. The projector reconstructs them from authenticated inputs. Every earlier-ranked candidate must be retained in the predecessor or carry a replay-verified reason it is not promotable. Rank skipping, incomplete negative evidence, a hand-authored candidate surface, or multiple possible first promotions fails closed.

## Authenticated input surfaces

Before deriving a selection, v2 replays and binds all of the following as distinct inputs:

- the v1 predecessor projection and its exact 100-row selection;
- the completed downstream materialization, including manifest, clearance, restriction, selected-document, and document-tree commitments;
- the sealed target-document eligibility audit that proves exactly one selected candidate is ineligible;
- the complete authenticated screened universe and its canonical candidate-ID mapping;
- the wider nonselected-candidate ledger and the full deterministic rank horizon;
- every source manifest, producer run card, and exact document byte used for a semantic repair or promoted packet;
- the provider-free clearance and restriction result for every promoted source document; and
- the linked opening motion, opposition, and first written disposition evidence required by the frozen cohort policy.

An input root is a locator, not authority. Each producer and output commitment is replayed from its exact bytes, and the v2 result is rejected if any source changes between verification and projection. Historical download presence, a docket label, or an internally consistent caller-authored directory cannot substitute for producer lineage.

## Config and promotion records

The closed config record uses `legalforecast.exact100_successor_replacement_config.v2`. It commits the fixed target count; v1 predecessor identity and selection; complete downstream materialization; stipulated-exclusion evidence; screened-universe and wider-ledger identity; deterministic ranking policy and horizon; semantic-repair records; promoted packet, clearance, restriction, and disposition-linkage evidence; exact output commitments; and false authority and activity flags.

Each canonical promotion record uses `legalforecast.exact100_successor_promotion.v2`. In addition to the promoted candidate and deterministic rank, it binds the authenticated source-selection row, repaired packet-role surface, complete required-document commitments, earlier-rank disposition horizon, and derived final selection row. A promotion record is an output of the replay, never an input that can select a candidate.

Retained selection rows remain byte-derived from the predecessor. The sole promoted row is derived from the authenticated screened-universe row plus the verified v2 packet surface. The final selection contains exactly 100 unique candidates, omits the sole sealed terminal candidate, and includes exactly one deterministic promotion.

## Completed state and authority boundary

`legalforecast.exact100_successor_replacement_state.v2` binds the config digest, all source and output commitments, predecessor, retained, excluded, promoted, and final counts, terminal and promoted candidate identities, and completed replay status. It records provider, CourtListener, PACER, RECAP Fetch, paid, model, evaluation, freeze, and dispatch activity and authority as false.

The v2 output may be consumed downstream only through its specialized replay verifier. A generic schema check or self-consistent state/config pair cannot mint successor-selection authority. Resume accepts only byte-identical completed outputs and replays the same authenticated inputs; it cannot recreate authority from saved output bytes alone.

This contract performs no network or provider call and grants no acquisition, labeling, evaluation, freeze, or dispatch capability. Any missing document, clearance decision, restriction proof, or semantic evidence stops the projection rather than widening the route.

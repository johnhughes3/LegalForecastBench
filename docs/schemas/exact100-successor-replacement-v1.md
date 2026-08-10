# Exact-100 successor replacement v1

`legalforecast.exact100_successor_replacement_config.v1` and `legalforecast.exact100_successor_replacement_state.v1` form a new, provider-free successor contract. They do not modify `legalforecast.zero_cost_successor_config.v1`, the frozen exact-100 reserve-extension contract, or the predecessor selection bytes.

The projector begins with a replay-verified `legalforecast.zero_cost_successor_config.v1` predecessor containing exactly 100 unique selected candidates. It may remove only candidates named in authenticated `legalforecast.exact100_successor_terminal_exclusion.v1` rows bound to that exact predecessor selection. It promotes the same number of candidates from a replay-verified reserve, strictly in frozen reserve-rank order. A promotion is permissible only when its complete public document, relevance, disclosure-clearance, restriction, and core-document artifacts pass the successor eligibility checks.

Retained selection rows are copied unchanged. The resulting selection must contain exactly 100 unique candidates; rank skipping, overlap with the predecessor or terminal subset, insufficient clean reserves, altered predecessor bytes, and incomplete promoted artifact surfaces are rejected.

## Config record and output surface

The closed config record has schema `legalforecast.exact100_successor_replacement_config.v1`. It commits:

- the fixed target case count;
- predecessor schema identity and predecessor-selection commitment;
- terminal-exclusion count and promoted candidate IDs;
- terminal-evidence and promotion-pool source commitments;
- exact output commitments; and
- false provider, paid, evaluation, freeze, and dispatch authority.

Every `source_commitments` entry is *derived*, never asserted. The production CLI first replays the authenticated zero-cost successor predecessor, then follows its authenticated input lineage to the original target projection. The predecessor capability is minted only from the zero-cost replay's exact output snapshots; the promotion pool is derived only from the original target projection's authenticated selection, frozen ranked reserve, relevance, manifest, clearance, restriction, and screening artifacts. A caller-owned, internally hash-consistent replacement-input directory is not an authority source and is rejected. The `require_verified_*` guards recompute the same digests so an artifact edited after verification fails closed even when the edit is invisible to the promotion rules. Predecessor keys are prefixed `predecessor_`, promotion-pool keys `reserve_`.

The output commitments cover the standard materialization files plus `successor-terminal-exclusions.jsonl` and `successor-promotions.jsonl`. The latter contains `legalforecast.exact100_successor_promotion.v1` rows with the candidate ID, frozen reserve rank, and canonical source-selection-row digest.

## Completed state

`legalforecast.exact100_successor_replacement_state.v1` is the completed terminal state. It binds the config digest and records predecessor, retained, terminal-exclusion, promotion, and final-selection counts; the terminal and promoted candidate IDs; and false provider, paid, evaluation, freeze, and dispatch state.

This contract is a deterministic projection boundary. It neither contacts CourtListener nor any model provider and it grants no paid acquisition, evaluation, freeze, or dispatch capability. Bounded noncharging recovery, if needed to establish a terminal-exclusion record, is a separately authenticated predecessor governed by [exact100-successor-terminal-exclusion-v1.md](exact100-successor-terminal-exclusion-v1.md).

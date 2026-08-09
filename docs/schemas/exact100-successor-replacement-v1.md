# Exact-100 successor replacement v1

`legalforecast.exact100_successor_replacement.v1` is the provider-free projection result for a post-selection exact-100 replacement.

It accepts no candidate IDs, SHA-256 strings, CourtListener responses, provider credentials, or paid-operation flags as authority.
Instead, it requires a verifier-minted sealed terminal authority that binds the exact source-pool, selected-cohort, ranked-reserve, and terminal-exclusion bytes.

The projection verifies that the selected cohort contains exactly 100 source-equivalent candidates; that terminal candidates are unique selected candidates; and that promotions use the first consecutive frozen reserve ranks without overlap or substitution.
It emits canonical successor-selection, terminal-exclusion, and promoted-reserve JSONL surfaces plus a self-hashed result record whose provider, paid, evaluation, freeze, and dispatch flags are all false.

This is an intentionally incomplete boundary: it does not itself issue terminal authority, retrieve a document, perform noncharging recovery, materialize a cohort, parse a PDF, or invoke Stage A or Stage B.
Those operations require their own authenticated, separately versioned producers before this result can become a downstream materialization input.

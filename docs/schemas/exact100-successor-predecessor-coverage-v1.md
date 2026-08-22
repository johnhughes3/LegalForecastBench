# Exact-100 successor predecessor coverage v1

`legalforecast.exact100_successor_predecessor_coverage.v1` is the frozen predecessor-artifact coverage contract used by exact-100 successor replacement v1. It does not reinterpret `legalforecast.zero_cost_successor_config.v1` or change any predecessor bytes.

Every selected document identity must appear on the predecessor download manifest, disclosure clearance, and restriction evidence. Case relevance must name the same document set as the selection row. Paid-recovery markers do not subtract identities from those three surfaces.

The v1 successor projector (`legalforecast.exact100_successor_replacement_config.v1`) always re-checks this coverage before emitting a v1 replacement config. A predecessor minted under a later coverage schema cannot silently satisfy v1 replacement.

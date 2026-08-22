# Exact-100 successor predecessor coverage v2

`legalforecast.exact100_successor_predecessor_coverage.v2` versions the predecessor-artifact coverage contract so a live zero-cost predecessor may keep unacquired selected documents as authenticated paid-recovery gaps. It does not reinterpret coverage v1, successor replacement v1, or any already-emitted v1 bytes.

A gap document is a selection identity whose `requires_paid_recovery` is exactly `True` and whose `availability_status` is exactly `"unavailable"`. Those identities remain on selection and case relevance. They are omitted from the pre-recovery download manifest, disclosure clearance, and restriction evidence. Acquired documents still require exact one-row coverage on those three surfaces. Inconsistent markers (one flag without the other) fail closed.

The production exact-100 successor replay mints the predecessor under this schema so Stage A can bind a live zero-cost predecessor that still has unpaid recovery gaps. The v1 replacement projector continues to require [coverage v1](exact100-successor-predecessor-coverage-v1.md) and will reject a v2-minted predecessor whose gaps would have failed the frozen contract.

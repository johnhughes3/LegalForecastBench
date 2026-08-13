# Exact-100 missing-document successor v1

`legalforecast.exact100_missing_document_acquisition_plan.v1` is the historical provider-free plan whose document identity is the pair `(candidate_id, docket_entry_number)`. It remains documented for verification of previously emitted artifacts and is superseded by v2 for selector-bearing repair plans.

The v1 plan accounts for every `missing_docs` row, sorts free CourtListener recovery ahead of PACER purchases, enforces the approved aggregate ceiling and per-document cap, and binds candidate, docket entry, asserted role, evidence, acquisition method, and projected cost. It cannot distinguish a main document from an attachment at the same docket entry.

`legalforecast.exact100_missing_document_successor.v1` is the corresponding historical sealed successor. New repairs use the v2 contract.

The sealed ledger is immutable and complete over planned acquisitions plus existing byte-role rejections. This contract grants no provider, purchase, evaluation, freeze, dispatch, or publication authority; an executor must obtain and verify those capabilities separately.

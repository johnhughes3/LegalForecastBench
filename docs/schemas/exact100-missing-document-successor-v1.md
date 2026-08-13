# Exact-100 missing-document successor v1

`legalforecast.exact100_missing_document_acquisition_plan.v1` is a provider-free plan derived from an observational repair-manifest sidecar whose exact raw SHA-256 and maximum spend were separately approved. The sidecar is evidence, not purchase authority. Planning performs no network or provider operation.

The plan accounts for every `missing_docs` row, sorts free CourtListener recovery ahead of PACER purchases, enforces the approved aggregate ceiling and `$3.00` per-document cap, and binds candidate, docket entry, asserted role, evidence, acquisition method, and projected cost. Every manifest byte-role mismatch is carried forward as an explicit rejection of the existing document.

`legalforecast.exact100_missing_document_successor.v1` is sealed only after each planned document is either admitted or explicitly excluded. Admission requires exact byte-count and SHA-256 agreement, the planned acquisition method, and a positive byte-vs-role validator result. An unplanned acquisition, free-to-paid substitution, role mismatch, or silent omission fails closed.

The sealed ledger is immutable and complete over planned acquisitions plus existing byte-role rejections. This contract grants no provider, purchase, evaluation, freeze, dispatch, or publication authority; an executor must obtain and verify those capabilities separately.

# Exact-100 missing-document successor v2

`legalforecast.exact100_missing_document_acquisition_plan.v2` is a provider-free plan derived from an observational repair-manifest sidecar whose exact raw SHA-256 and maximum spend were separately approved. The sidecar is evidence, not purchase authority. Planning performs no network or provider operation.

The plan accounts for every `missing_docs` row, sorts free CourtListener recovery ahead of PACER purchases, enforces the approved aggregate ceiling and per-document cap, and binds candidate, docket entry, `document_selector` (`main_document` or `attachment_N`), asserted role, evidence, acquisition method, and projected cost. The selector keeps a main document and supporting attachment at the same docket entry distinct throughout planning and sealing. Every manifest byte-role mismatch is carried forward as an explicit rejection of the existing document.

`legalforecast.exact100_missing_document_successor.v2` is sealed only after each planned document is either admitted or explicitly excluded. Admission requires exact byte-count and SHA-256 agreement, the planned acquisition method, and a positive byte-vs-role validator result. An unplanned acquisition, free-to-paid substitution, role mismatch, or silent omission fails closed.

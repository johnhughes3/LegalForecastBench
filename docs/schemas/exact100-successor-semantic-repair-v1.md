# Exact-100 successor semantic repair v1

`legalforecast.exact100_successor_semantic_repair.v1` is a provider-free, evidence-bound correction to document-role metadata used only by the exact-100 successor replacement v2 contract. It does not change authenticated source bytes, edit a historical manifest, or authorize retrieval, provider, paid, evaluation, freeze, or dispatch activity.

The repair exists for a narrow failure mode: authenticated document bytes contain a required packet component even though the historical docket-derived role does not describe that component completely. The supported `repair_kind` findings are:

- `embedded_operative_amended_complaint`: an authenticated removal or other court-filed bundle contains the operative amended complaint; and
- `combined_mtd_memorandum`: a document historically classified as a motion notice is a combined motion and substantive supporting memorandum.

The verifier derives each finding from exact source-document bytes and fixed semantic cues. A caller cannot supply a replacement candidate, repaired role, excerpt, page range, or conclusion that the verifier merely trusts. Original document identifiers and historical roles remain committed in the record; the derived role applies only inside the v2 successor replay.

## Closed evidence record

Each canonical repair record contains exactly:

- `schema_version`;
- `candidate_id`;
- `source_document_id`;
- `docket_entry_number`, an integer or `null`;
- `original_document_role`;
- `derived_document_role`;
- `repair_kind`, one of the two closed values above;
- `source_sha256`, the lowercase raw-file SHA-256;
- `source_byte_count`;
- `source_metadata_sha256`, the `sha256:`-prefixed canonical commitment to the complete original source-metadata record; and
- `evidence_cues`, an ordered nonempty list of closed `{cue, page_number}` objects.

The embedded-operative-amended-complaint finding must identify page-bounded cues in the source bundle that establish the identified pleading as the operative amended complaint. The combined-MTD-memorandum finding must prove that the same filed document both moves to dismiss the operative complaint and contains substantive points and authorities. A title or docket label alone is insufficient.

Repairs are looked up only by the exact `(candidate_id, source_document_id)` pair. The derived role augments the authenticated original role inside v2 and never mutates the source metadata. A record fails closed for changed bytes, identity drift, an unsupported repair kind, inconsistent original or derived roles, missing or out-of-range evidence cues, incomplete producer lineage, or any extra field. A repair for one document cannot be replayed against another copy or candidate even when their text is similar.

## Authority boundary

Canonical serialization proves the integrity of the repair record, not the underlying conclusion. The verifier-owned in-process capability preserves the complete canonicalized original metadata tuple, exact source bytes, source commitments, canonical repair records and bytes, and their commitment. The v2 successor verifier must independently replay that capability's authenticated producer lineage and reconstruct the record from the exact bytes before using the derived role. Persisted repair JSONL is never accepted as a free-standing authority source.

This contract does not replace the model-backed packet-role adjudication protocol and does not grant a general role-override mechanism. Unsupported or ambiguous role corrections remain ineligible until a separately authorized, versioned path authenticates them.

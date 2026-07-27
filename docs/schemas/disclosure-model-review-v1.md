# Disclosure model review v1

Cycle 1 freezes exactly one non-evaluation acquisition reviewer in `model_registries/cycle-1-disclosure-reviewer-2026-07-27.json`: `google:gemini-3.5-flash`.
Before use, its provider, model ID, and exact key must each be proven absent from the frozen evaluated-model registry.
This registry does not authorize provider calls, spending, evaluation, freeze, or dispatch.

`legalforecast.disclosure_model_review_prompt.v1` is a deterministic canonical-JSON private document prompt over exact PDF bytes.
It includes only pages on which the v3 scanner reproduces a declared substantive marker.
Evidence text is JSON encoded and explicitly declared inert and untrusted, so text resembling tags or instructions cannot alter the prompt structure.
The prompt asks only whether public-court text exposes sensitive personal information; it forbids merits or disposition analysis and requires quarantine on uncertainty.
The requested supporting excerpt is closed to 20 through 240 characters of verbatim marker-page text and must itself contain text that reproduces at least one declared marker; if the entire marker page is shorter than 20 characters, the whole page is the permitted lower-bound exception.
The frozen reviewer allows 16,384 output tokens so the one-call 14-document response has ample headroom under that excerpt bound.

`legalforecast.disclosure_model_review_batch_prompt.v1` and `legalforecast.disclosure_model_review_batch_response.v1` are the closed single-call envelopes.
A nonempty ordered document set, including 14 documents, produces one batch prompt and exactly one raw provider response per authenticated batch-attempt identity.
That verifier-owned attempt identity must bind the authenticated execution evidence, attempt ordinal, and exact batch-prompt hash to one private raw-response artifact.
A bounded retry is a distinct next attempt identity with a distinct private raw-response artifact; it must never overwrite or replace the first attempt's raw artifact, combine responses across attempts, or make either attempt appear to have more than one response.
The batch response contains one ordered `legalforecast.disclosure_model_review_response.v1` semantic item per document.
The exact raw batch bytes have one batch-level hash; each semantic item separately has the hash of its canonical JSON bytes.
Prompt hashes are verifier-owned transport commitments: model-generated JSON does not contain or echo either the batch prompt hash or per-document prompt hashes.
The validator derives those commitments from the exact prompt objects supplied alongside the raw response.
The batch response fields are exactly `schema_version`, `model_id`, `model_version`, `document_count`, and `items`.
The batch prompt carries those fields, the exact semantic-item fields, allowed enum values, decision relationship, excerpt rule, frozen reviewer model ID and version, and the complete registry-entry SHA-256, so the provider is not expected to infer an out-of-band schema and a same-ID reviewer configuration cannot be rebound after prompting.

`legalforecast.disclosure_model_review_response.v1` is therefore a per-document semantic record, not a raw provider response.
Its fields are exactly `schema_version`, `candidate_id`, `source_document_id`, `document_sha256`, `model_id`, `model_version`, `decision`, `sensitive_content`, `supporting_page_number`, and `supporting_excerpt`.
Candidate, document, and declared registry-model identities must match.
The authenticated transport served-version metadata is authoritative.
The model-generated `model_version` must exactly equal that authenticated served version; a missing or different value rejects the entire batch before any private or public projection.
Downstream projections must derive any served-version value from the authenticated transport evidence and must never trust or copy the model-generated `model_version` field.
The supporting excerpt must satisfy the prompt’s length, marker, and verbatim-page constraints.
A response may clear only when `sensitive_content` is `absent`; `present` and `uncertain` require quarantine.

`legalforecast.disclosure_model_review_decision.v1` is the public per-document projection.
It contains candidate and source-document identities, document, document-prompt, batch-prompt, semantic-response, raw-batch-response, and reviewer-entry hashes, plus terminal status.
It contains no page text, prompt text, supporting excerpt, rationale, or raw provider output.
It intentionally contains no caller-supplied per-document cost.

Typed validated reviews are projected into canonical private JSONL containing the verbatim excerpt and exact document, prompt, response, reviewer-entry, page, identity, and status commitments.
This pure core does not authenticate execution and therefore does not export authority or a public run card.
Future integration must derive authority from verifier-owned local journal readback, authenticated remote-call evidence, raw-payload re-decoding, independently frozen registry identities, and cross-store agreement.
It must treat a nonempty document batch as one provider attempt, or two only after the bounded retry, rather than one attempt per document.
This foundation defines validation contracts only and does not authorize provider calls, retries, spending, evaluation, freeze, or dispatch.
Raw page text, prompts, provider responses, and supporting excerpts remain private.

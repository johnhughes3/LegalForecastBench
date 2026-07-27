# Disclosure model review v1

Cycle 1 freezes exactly one non-evaluation acquisition reviewer in `model_registries/cycle-1-disclosure-reviewer-2026-07-27.json`: `google:gemini-3.5-flash`.
Before use, its provider, model ID, and exact key must each be proven absent from the frozen evaluated-model registry.
This registry does not authorize provider calls, spending, evaluation, freeze, or dispatch.

`legalforecast.disclosure_model_review_prompt.v1` is a deterministic canonical-JSON private document prompt over exact PDF bytes.
It includes only pages on which the v3 scanner reproduces a declared substantive marker.
Evidence text is JSON encoded and explicitly declared inert and untrusted, so text resembling tags or instructions cannot alter the prompt structure.
The prompt asks only whether public-court text exposes sensitive personal information; it forbids merits or disposition analysis and requires quarantine on uncertainty.

`legalforecast.disclosure_model_review_batch_prompt.v1` and `legalforecast.disclosure_model_review_batch_response.v1` are the closed single-call envelopes.
A nonempty ordered document set, including 14 documents, produces one batch prompt and exactly one raw provider response.
The batch response contains one ordered `legalforecast.disclosure_model_review_response.v1` semantic item per document.
The exact raw batch bytes have one batch-level hash; each semantic item separately has the hash of its canonical JSON bytes.

`legalforecast.disclosure_model_review_response.v1` is therefore a per-document semantic record, not a raw provider response.
Candidate, document, prompt, and declared registry-model identities must match.
The eventual served-version claim must come from authenticated provider transport metadata, not model-generated JSON.
The supporting excerpt must be verbatim text from the declared marker page.
A response may clear only when `sensitive_content` is `absent`; `present` and `uncertain` require quarantine.

`legalforecast.disclosure_model_review_decision.v1` is the public per-document projection.
It contains candidate and source-document identities, document, prompt, semantic-response, raw-batch-response, and reviewer-entry hashes, plus terminal status.
It contains no page text, prompt text, supporting excerpt, rationale, or raw provider output.
It intentionally contains no caller-supplied per-document cost.

Typed validated reviews are projected into canonical private JSONL containing the verbatim excerpt and exact document, prompt, response, page, identity, and status commitments.
This pure core does not authenticate execution and therefore does not export authority or a public run card.
Future integration must derive authority from verifier-owned local journal readback, authenticated remote-call evidence, raw-payload re-decoding, independently frozen registry identities, and cross-store agreement.
It must treat a nonempty document batch as one provider attempt, or two only after the bounded retry, rather than one attempt per document.
Raw page text, prompts, provider responses, and supporting excerpts remain private.

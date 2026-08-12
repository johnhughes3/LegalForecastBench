# Stage A unitizer terminal escalation v1

`legalforecast.llm_stage_a_unitizer_terminal_escalation.v1` is an immutable, provider-free receipt for one selected `claim-ontology-v5` unitizer call whose three normal reconstruction attempts are all durably `reconstruction_failed`.

The closed record contains:

- `candidate_id` and `case_id`;
- `unitizer_model_key`, lowercase `model_registry_sha256`, and `provider_attempt_namespace`;
- the exact frozen `prompt` and its lowercase `prompt_sha256`;
- a nonempty ordered `predecision_source_commitments` array, each with `source_document_id`, `document_role`, positive-or-null `docket_entry_number`, `description`, and prefixed `markdown_sha256`; and
- exactly three ordered `failed_attempts`, with ordinals 1, 2, and 3 and, for each attempt, prefixed raw and normalized response SHA-256 values plus nonempty failure type and message.

The producer reconstructs the logical call from the authenticated selection, parser output, Markdown tree, registry, v5 prompt contract, caps, and canonical provider journal. It requires exact identity across all three journal rows, complete raw and normalized failure evidence, no reconstructed result, and no changed input. It reads a query-only journal snapshot, writes only the receipt and its provider-free completion record, and proves the journal's provider-attempt projection is unchanged.

The receipt contains no proposed prediction unit and accepts no failed response. Fewer or more attempts, a skipped ordinal, any non-failed status, incomplete failure evidence, prompt/source/model/cycle drift, a duplicate source, an invalid digest, or any attempt to use a namespace other than `claim-ontology-v5` fails closed. It neither permits nor performs a fourth provider call.

The canonical digest of the complete receipt is the `terminal_escalation_sha256` used by the terminal queue, attorney packet, adjudication, and finalized-unit chain.

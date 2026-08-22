# Manifest cost projection receipt v1

`legalforecast.manifest_cost_projection_receipt.v1` is the canonical provider-free receipt emitted by `legalforecast acquisition project-manifest-cost` from local manifest forecast run-input bytes and a frozen model registry.

The receipt commits the exact raw input bytes by lowercase SHA-256 and byte length; records the requested model keys, ablations, case order, repeat sample, repeat count, optional dispatch ceiling, and matrix limit; and carries the full matrix, provider matrices and counts, packet/ablation count, model count, long-context warning rows, projected model cost, and recommended two-times early-warning ceiling.

Cost uses the official workflow formula `(input_tokens * input_token_price + max_output_tokens * output_token_price) / 1_000_000` for each packet/model row, multiplied by the row repeat count. Packet tokens use this fallback order: `estimated_input_tokens`, `input_tokens`, `prompt_tokens`, `estimated_prompt_tokens`, `packet_token_count`, `token_count`, then `ceil(packet_size_bytes / 4)`. Packets above 272,000 estimated input tokens are warning rows; the receipt preserves the workflow behavior of flagging them for deliberate pricing or exclusion without silently applying a registry surcharge multiplier.

The projected and recommended USD fields are fixed six-place decimal strings, while an optional operator-supplied dispatch ceiling retains its accepted decimal spelling. The optional ceiling must be at least the exact unrounded projection and no more than twice that projection. It is an early-warning control, not a provider or account cap.

Issuance is create-only and rechecks the two input byte snapshots immediately before and after publication. It performs no provider call, AWS action, spend reservation, packet mutation, dispatch, or publication of benchmark results.

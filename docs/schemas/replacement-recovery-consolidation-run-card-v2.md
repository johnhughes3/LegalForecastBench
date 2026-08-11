# Replacement recovery consolidation run card v2

Schema identifier: `legalforecast.replacement_recovery_consolidation_run_card.v2`.

This Cycle 1 correctness migration preserves the v1 consolidation card and output semantics while replacing the legacy caller-selected purchased-manifest sidecar with an authenticated exact-100 successor-v2 target root.

A v2 card has the same completed provider-free stage, output commitments, purchase-state binding, and terminal-omission partition as v1, plus `target_projection_mode: "exact100_successor_replacement_v2"`.

`input_paths[3]` is the authenticated target root rather than a purchased-manifest file. The verifier replays that root through `legalforecast.exact100_successor_replacement_state.v2`, requires the caller's selection path to be the exact replay-authenticated selection, derives any inherited purchased partition from that replay, and commits every authenticated target artifact file returned by the replay. The caller cannot supply or synthesize a purchased-manifest sidecar in target-root mode.

The schema does not authorize retrieval, purchase, provider, evaluation, freeze, or dispatch activity.

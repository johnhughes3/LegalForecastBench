# Harness efficiency and accounting observations

Published community tables treat duration, cost, and token accounting as
peer columns next to score and coverage. The observation is a
non-authoritative sidecar bound to the existing `RunSpec` /
`ExecutionReceipt` pair and optional `EvaluationReceipt`. It is not a
second receipt family.

The schema id is `legalforecast.multiharness.harness_efficiency_observation.v1`.
Package it as `efficiency-observation.json` next to the community
submission. Aggregate and site renderers reconstruct every displayed
figure from that file and from `score-artifacts.jsonl`.

## Definitions

- **solve_tokens** — Provider-reported solver tokens from
  `ExecutionReceipt.usage`. When `total_tokens` is present it is used
  as-is. Otherwise `input_tokens` plus `output_tokens`. Cache-read,
  cache-write, and reasoning tokens are dimensions and are never added on
  top of a reported total.
- **eval_tokens** — Evaluator tokens from
  `EvaluationReceipt.token_usage.total_tokens`. Missing totals stay null
  with a reason; zeroes are never inferred.
- **total_tokens** — Solve tokens plus eval tokens when both are known.
  Null with reason when either side is unknown. Retry receipts are
  counted once per `receipt_id`.
- **solve_cost** — `ExecutionReceipt.cost_usd` converted to micro-USD
  with basis `provider_reported`. Null cost is unknown, never `$0`.
  `subscription_unallocable` cannot carry an amount. A local-CLI run
  reports null here unless its stdout drain read that stream through to
  end of file: the trailing cost envelope may still have been in the
  pipe, so the newest object in the rolling tail is an earlier one and
  is not published. A stderr drain that missed its join still marks the
  receipt truncated, but it says nothing about stdout and does not
  suppress an amount parsed from a completed stdout tail.
- **eval_cost** — `EvaluationReceipt.cost`, including its basis,
  currency, and `pricing_snapshot_sha256`. `subscription_unallocable`
  remains null.
- **combined_cost** — Sum of solve and eval costs only when bases and
  currencies are compatible. Ratios are refused across estimated vs
  metered bases or across currencies. `subscription_unallocable` never
  enters a ratio as `$0`.
- **wall_elapsed_ms** — Process wall-clock from
  `ExecutionReceipt.duration_ms`. Parallel work does not inflate this
  clock.
- **summed_call_elapsed_ms** — Sum of per-call monotonic elapsed time
  from `EvaluationReceipt.timing.summed_call_elapsed_ns`, converted to
  milliseconds. This may differ from `wall_elapsed_ms`.
- **attempt_count** — Number of unique `ExecutionReceipt` `receipt_id`s
  observed.
- **retry_count** — Attempts beyond the first unique receipt. Retries
  contribute to `attempt_count` once each and are not double-counted in
  token totals.
- **failure_count** — Receipts whose status is not `succeeded`.

A single repeat publishes observed values only. Sample variance and
ranking statistics require at least two repeats.

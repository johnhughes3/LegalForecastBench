# Acquisition Cycle Configuration v1

`legalforecast.acquisition_cycle_config.v1` is the immutable operator plan consumed by `legalforecast acquisition run-cycle`.

The coordinator is deliberately acquisition-only.
It cannot call evaluation, freeze, dispatch, publication, or legacy paid Case.dev commands.
It delegates every permitted stage to the existing `legalforecast acquisition <command>` handler, so the stage's own eligibility, disclosure, provider-authority, purchase-policy, ledger, and budget checks remain authoritative.

## Canonical configuration

The file is canonical UTF-8 JSON as produced by `legalforecast.ingestion.disclosure_review_bundle.canonical_json_bytes`.
The coordinator reads it as a unique regular file, hashes its exact bytes, and binds that SHA-256 into every immutable stage receipt.
Changing the file after any stage is receipted makes resume fail closed.

The top-level object has exactly:

- `schema_version`: `legalforecast.acquisition_cycle_config.v1`.
- `cycle_id`: a lowercase safe identifier.
- `eligibility_anchor`: an ISO date.
- `target_case_count`: a positive integer; use `100` for the launch cohort.
- `stages`: the complete ordered list of coordinator-supported, completion-card-emitting acquisition stages in this plan.

Some deterministic policy generators do not yet emit the common acquisition completion card and therefore remain explicit direct commands in the official runbook.
Do not represent them as already completed coordinator stages.

Each stage has exactly:

- `id`: a unique lowercase safe identifier.
- `command`: a command on the coordinator's reviewed acquisition allowlist.
- `boundary`: the command's fixed reviewed boundary; an operator cannot downgrade it.
- `arguments`: the exact arguments after `legalforecast acquisition <command>`.
- `run_card`: the absolute completion-card path.
- `run_card_stage`: the exact `stage` value expected in that card.

Every stage must include `--execute` and exactly one `--run-card-output` equal to `run_card`.
`--no-resume` is forbidden.
Paths and hashes passed to an underlying stage remain subject to that stage's stronger verification.

## Boundaries

The default `--execute` invocation advances only `provider_free` stages.
It stops before:

- `network`: free CourtListener, Firecrawl, Case.dev, or document-download activity; enable only with `--allow-network`.
- `human`: purchase approval or adjudication/reviewer work; enable only with `--allow-human`.
- `model_provider`: Mistral parsing or labeling-model calls; enable only with both `--allow-network` and `--allow-model-provider`.
- `paid`: CourtListener RECAP Fetch document purchases; enable only with both `--allow-network` and `--allow-paid`.

Those switches merely let the coordinator invoke the existing command.
They do not supply credentials, create authority, acknowledge fees, expand a budget, or bypass any underlying gate.
Paid execution therefore still requires the exact approved purchase policy, initialized canonical ledger, attempt policy, broker policy, deployed broker identity, and budget state required by `purchase-missing-recap-fetch`.

## Receipts and resume

After a stage returns success, the coordinator reopens its run card through a no-follow race-checked read, requires an executed completed card for the configured stage, and writes:

```text
<state-root>/receipts/<zero-padded-index>-<stage-id>.json
```

The canonical receipt binds the configuration SHA-256, stage index and identity, command arguments SHA-256, boundary, run-card path, run-card stage, and exact run-card SHA-256.
On resume, the receipt and run card are both reauthenticated before the stage is skipped.
An unreceipted run card is never silently adopted: the existing command must successfully replay under `--resume` before the coordinator creates its receipt.

Status-only mode creates no state and returns the exact next invocation.
JSON output is selected with `--json` and is also the default when stdout is not a TTY.
`status: completed` and `plan_completed: true` mean that every stage listed in this configuration is receipted; they do not alone claim that the corpus target was met.
Only a plan ending in a successful `finalize-corpus --target-clean-cases <target_case_count>` reports `corpus_target_verified: true` and a non-null `clean_case_count`.

## Minimal shape

The following illustrates one provider-free first stage; replace every absolute path for the new cycle and serialize the object canonically:

```json
{"cycle_id":"cycle-next","eligibility_anchor":"2026-06-30","schema_version":"legalforecast.acquisition_cycle_config.v1","stages":[{"arguments":["--output-root","/absolute/artifacts/cycle-next/acquisition","--eligibility-anchor","2026-06-30","--run-card-output","/absolute/artifacts/cycle-next/acquisition/run-cards/init-cycle.json","--execute"],"boundary":"provider_free","command":"init-cycle","id":"initialize","run_card":"/absolute/artifacts/cycle-next/acquisition/run-cards/init-cycle.json","run_card_stage":"init-cycle"}],"target_case_count":100}
```

Inspect without mutation:

```bash
uv run legalforecast acquisition run-cycle \
  --config /absolute/manifests/cycle-next.acquisition-cycle.json \
  --state-root /absolute/artifacts/cycle-next/orchestrator \
  --json
```

Advance provider-free stages only:

```bash
uv run legalforecast acquisition run-cycle \
  --config /absolute/manifests/cycle-next.acquisition-cycle.json \
  --state-root /absolute/artifacts/cycle-next/orchestrator \
  --execute --json
```

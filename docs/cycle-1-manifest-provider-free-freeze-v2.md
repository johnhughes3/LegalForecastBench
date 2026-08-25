# Cycle 1 manifest provider-free freeze v2

This run card issues and verifies the replacement manifest execution commitments without provider, AWS, dispatch, scoring, or publication activity. Every output parent directory must already exist, and all output locations must be new: the issuers are create-only and will not replace an existing file or directory.

Issue and replay-verify the execution decisions and additive policy v2. The critical issuer itself runs `bd comments legalforecastbench-3ak.38 --json` and publishes the authenticated replay wrapper inside the output tree; it does not accept a caller-supplied Beads observation.

```bash
uv run legalforecast acquisition issue-manifest-execution-decisions-v2 \
  --owner-manifest "$OWNER_MANIFEST" \
  --forecast-output-dir "$FORECAST_OUTPUT_DIR" \
  --model-registry "$MODEL_REGISTRY" \
  --provider-cycle-caps "$EVALUATION_PROVIDER_CAPS" \
  --labeling-provider-cycle-caps "$LABELING_PROVIDER_CAPS" \
  --provider-journal "$LABELING_PROVIDER_JOURNAL" \
  --labeling-policy "$LABELING_POLICY" \
  --cohort-policy "$COHORT_POLICY" \
  --cohort-observation-manifest "$COHORT_OBSERVATION" \
  --freeze-inputs-root "$GENERIC_FREEZE_ROOT" \
  --output-root "$EXECUTION_DECISIONS_ROOT"

uv run legalforecast acquisition verify-manifest-execution-decisions-v2 \
  --output-root "$EXECUTION_DECISIONS_ROOT"
```

Then issue and replay-verify the labels-deferred forecast bundle using the generated v2 policy:

```bash
uv run legalforecast acquisition issue-manifest-forecast-bundle-v2 \
  --cycle-id cycle-1 \
  --freeze-inputs-root "$GENERIC_FREEZE_ROOT" \
  --owner-manifest "$OWNER_MANIFEST" \
  --forecast-output-dir "$FORECAST_OUTPUT_DIR" \
  --model-registry "$MODEL_REGISTRY" \
  --provider-cycle-caps "$EVALUATION_PROVIDER_CAPS" \
  --execution-policy "$EXECUTION_DECISIONS_ROOT/execution-policy-v2.json" \
  --output-root "$DEFERRED_BUNDLE_ROOT"

uv run legalforecast acquisition verify-manifest-forecast-bundle-v2 \
  --output-root "$DEFERRED_BUNDLE_ROOT"
```

Once the locked labels exist, bind those exact bytes and the verified v2 policy into the ordinary final 13-artifact freeze. The legacy `verify-execution-policy` command remains v1-only; final freeze, official per-case execution, dispatch provenance, and fan-in explicitly accept either authenticated v1 or v2 policy bytes. The final freeze output is create-only.

```bash
uv run legalforecast freeze cycle-1-target-100-2026-07-25 \
  --manifest "$OWNER_MANIFEST" \
  --units "$PREDICTION_UNITS" \
  --labels "$LOCKED_LABELS" \
  --prompt "$GENERIC_FREEZE_ROOT/prompt-contract.json" \
  --scorer "$GENERIC_FREEZE_ROOT/scorer-contract.json" \
  --harness "$GENERIC_FREEZE_ROOT/harness-contract.json" \
  --model-registry "$MODEL_REGISTRY" \
  --baselines "$GENERIC_FREEZE_ROOT/no-baselines.json" \
  --exclusion-ledger "$GENERIC_FREEZE_ROOT/complete-exclusion-ledger.jsonl" \
  --provider-cycle-caps "$EVALUATION_PROVIDER_CAPS" \
  --execution-policy "$EXECUTION_DECISIONS_ROOT/execution-policy-v2.json" \
  --labeling-policy "$LABELING_POLICY" \
  --cohort-policy "$COHORT_POLICY" \
  --bundle-output "$FINAL_FREEZE"

uv run legalforecast freeze verify \
  --bundle "$FINAL_FREEZE" \
  --cycle-id cycle-1-target-100-2026-07-25
```

Successful verification proves only that the local provider-free commitment trees and labels-bound final freeze reproduce from their authenticated inputs. It does not authorize or claim provider calls, AWS operations, protected-workflow dispatch, scoring, or publication.

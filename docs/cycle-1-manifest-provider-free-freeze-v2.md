# Cycle 1 manifest provider-free freeze v2

This run card issues and verifies the replacement manifest execution commitments without provider, AWS, dispatch, scoring, or publication activity. All output locations must be new: the issuers are create-only and will not replace an existing file or directory.

First capture the live coordination comments into an authenticated replay wrapper:

```bash
uv run legalforecast acquisition issue-manifest-execution-decisions-beads-observation-v2 \
  --model-registry "$MODEL_REGISTRY" \
  --output "$BEADS_OBSERVATION"
```

The command itself runs `bd comments legalforecastbench-3ak.38 --json`. There is no argument for caller-supplied comment JSON.

Issue and replay-verify the execution decisions and additive policy v2:

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
  --beads-observation "$BEADS_OBSERVATION" \
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

Successful verification proves only that the local provider-free commitment trees reproduce from their authenticated inputs. It does not authorize or claim provider calls, AWS operations, protected-workflow dispatch, label attachment, scoring, or publication.

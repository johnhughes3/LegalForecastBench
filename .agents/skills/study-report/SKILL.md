---
name: study-report
description: Run a reproducible LegalForecast evaluation study report from public release artifacts.
---

# Study reports

Use the public CLI to evaluate a frozen study specification against persisted
run receipts:

```bash
legalforecast study report \
  --spec study-spec.json \
  --inputs study-inputs.json \
  --output study-report.json
```

The specification is a `legalforecast.study-spec.v1` JSON object. The inputs
file is either a direct object mapping arm IDs to artifact paths or an object
with an `arms` field containing that mapping. Each arm entry names
`forecast_release`, `labels_release`, `manifest`, `model_registry`, and
`run_records` paths. Paths are resolved relative to the inputs file; an
optional `artifact_root` may be supplied globally, per arm, or on the command
line. Set `run_records` to `null`, or omit the arm, to preserve a missing-arm
observation. Receipts are persisted JSONL objects; a JSON array is also
accepted for small public fixtures.

The command validates public releases, manifests, registries, and receipts and
delegates strict scoring and study inference to `evaluate_study`. It does not
run models, contact providers, access private data, or accept aggregate scores
as evidence. The output is the canonical
`legalforecast.study-report.v1` JSON object.

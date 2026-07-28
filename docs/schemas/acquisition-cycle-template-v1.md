# Acquisition Cycle Template v1

`legalforecast acquisition render-cycle-config` turns one canonical path-parameterized template into the immutable configuration consumed by `acquisition run-cycle`.

The renderer exists so a new acquisition cycle does not depend on shell history or machine-specific hand edits.
It performs no provider call, purchase, evaluation, freeze, or dispatch.

## Template shape

The template is canonical UTF-8 JSON with exactly:

- `schema_version`: `legalforecast.acquisition_cycle_template.v1`
- `completion_mode`: `corpus` for a production plan that must end in `finalize-corpus`, or `partial` for an explicitly incomplete migration/rehearsal fragment
- `variables`: the unique uppercase names of every absolute path supplied at render time
- `config`: one complete `legalforecast.acquisition_cycle_config.v1` object

Placeholders use the exact `${NAME}` form and may appear only in string values under `config`.
Every declared variable must be used and every placeholder must be declared.
The renderer requires exactly one `--variable NAME=/absolute/path` assignment for each declaration; it rejects missing, duplicate, extra, empty, or relative assignments.
It does not read environment variables or perform recursive expansion.

The rendered config is passed through the ordinary `run-cycle` validator before publication.
That validator remains authoritative for the acquisition command allowlist, stage boundaries, eligibility anchor, target count, exact `--run-card-output` values, deterministic resume, and final corpus target.
A `corpus` template is additionally rejected unless its last stage is `finalize-corpus`; a `partial` render states that it does not prove corpus completion and must not be used as the official full-cycle plan.

## Publication

The output directory must already exist, resolve without symlinks, and remain the same directory identity throughout publication; the output path must not already exist.
The renderer validates the bytes before writing, opens the parent and new file through no-follow directory descriptors, publishes without replacement, fsyncs, and reopens the final unique regular file through the anchored directory descriptor.
The JSON receipt printed to stdout records the template and output hashes, cycle identity, target, and stage count.

Future stage outputs do not need to exist when the config is rendered.
Their paths are immutable names that the stage and receipt verifier authenticate when execution reaches them.
Literal content-derived hashes or remote workflow identities that are command arguments must already be known before rendering; never change a config after its first receipt.

## Example

```bash
uv run legalforecast acquisition render-cycle-config \
  --template manifests/cycle-next.acquisition-cycle.template.json \
  --variable REPO_ROOT="$PWD" \
  --variable ARTIFACT_ROOT="$PWD/artifacts/cycle-next" \
  --variable PRIVATE_ROOT="/absolute/private/cycle-next" \
  --output "$PWD/artifacts/cycle-next/acquisition-cycle.json"

uv run legalforecast acquisition run-cycle \
  --config "$PWD/artifacts/cycle-next/acquisition-cycle.json" \
  --state-root "$PWD/artifacts/cycle-next/orchestrator" \
  --json
```

Direct deterministic generators that do not emit the common acquisition completion card remain explicit prerequisite commands in the cycle runbook.
Do not misrepresent them as completed coordinator stages.

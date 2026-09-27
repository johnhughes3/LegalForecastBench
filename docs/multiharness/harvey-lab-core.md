# Native Harvey LAB bridge

`legalforecast harvey-lab` runs the public Harvey LAB `lab-core` 1.1.0 workflow: native solving first, then a separately selected single judge. It is a non-official community comparison, not an official LegalForecast-MTD forecast or a reproduction of Harvey's published dual-judge baseline. Harvey LAB is a separate [Harvey AI project](https://github.com/harveyai/harvey-labs), distributed under the MIT license. No sponsorship, partnership, or endorsement is implied.

The supported source is commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`, tree `bc7e16d2b5b794b86624288506a5d0be17c1052b` (upstream tag `v1.1.0`). Both the clean checkout and installed `lab_core` package bytes must match. Historical comparison commands retain their older pin; the fixture-only `harvey-lab` adapter is not this native bridge.

## Prepare and probe without providers

Install the pinned package in its own Python 3.12 or 3.13 environment, outside the source checkout. For example, from a contributor workspace:

```bash
git clone https://github.com/harveyai/harvey-labs.git harvey-labs
git -C harvey-labs checkout --detach 1dd81403b2fbb60596f7aea3fcecafad7bf73143
UV_PROJECT_ENVIRONMENT="$PWD/lab-core-env" uv sync --frozen --project harvey-labs
```

From an installed LegalForecastBench environment, use the resulting absolute paths:

```bash
legalforecast harvey-lab probe \
  --source-root "$LAB_CORE_ROOT" \
  --python "$LAB_CORE_PYTHON" \
  --output-dir lab-probe
```

The probe verifies source/package/interpreter identity and executes both real CLI `--help` entrypoints. It passes no provider credentials. Diagnostics remain in the scratch directory, including stderr. It does not execute a model, a judge, or a benchmark task.

The native solver requires Linux rootless Podman and a prepared LAB sandbox image. Build the upstream Dockerfile, then select its immutable image ID:

```bash
podman build --file "$LAB_CORE_ROOT/lab_core/sandbox/Dockerfile" \
  --tag lab-core-v1.1.0 "$LAB_CORE_ROOT/lab_core/sandbox"
LAB_IMAGE_ID="$(podman image inspect lab-core-v1.1.0 --format '{{.Id}}')"
LAB_IMAGE_ID="sha256:${LAB_IMAGE_ID#sha256:}"
```

Podman must find that image through the contributor's normal `XDG_DATA_HOME` storage (or its default). The bridge preserves that data path and the validated local runtime directory, but isolates home/config directories. Custom Podman configuration or remote Podman services are not supported by this bridge. A missing image fails before provider execution; the bridge does not authorize an implicit pull/build during a run. Install upstream evaluator system dependencies such as Pandoc before a DOCX evaluation.

## Contributor-funded run

Obtain an explicit fresh approval covering both solver and judge costs before running. Use provider-side spending limits for the approved exposure: LAB's `--max-turns` and the command timeout are not dollar caps. This bridge does not implement its own model loop, retry purchases, or obtain credentials. Model IDs are passed unchanged to upstream; the judge must be one supported upstream judge ID, not a comma-separated pair.

```bash
legalforecast harvey-lab run \
  --source-root "$LAB_CORE_ROOT" \
  --python "$LAB_CORE_PYTHON" \
  --task-id harvey_lab:employment-labor/identify-issues-in-counterparty-motion-brief \
  --model "$SOLVER_MODEL" --judge-model "$JUDGE_MODEL" \
  --run-id contributor-smoke-1 --max-turns 10 \
  --sandbox-image "$LAB_IMAGE_ID" \
  --provider-env OPENAI_API_KEY --provider-env ANTHROPIC_API_KEY \
  --output-dir lab-one-task
```

Pass only the credential names the chosen solver and judge need; remove unused grants. Environment inheritance is allowlisted, dotenv discovery is disabled, and the private `LAB_ROOT` contains no `.env`. The model operates inside upstream's network-disabled sandbox over the task documents, output, and workspace, not the host-side grading rubric. The upstream package owns all agent execution.

Task IDs accept either `harvey_lab:category/task` or `category/task`. The upstream run directory is deterministically derived from task, exact model, and contributor run ID. Each invocation requires a fresh output directory. It copies the selected pinned task/documents, supports upstream shared document directories, and calls:

```text
python -B -I -m lab_core.harness.run --task ... --model ... --run-id ... --max-turns ... --sandbox-image ...
python -B -I -m lab_core.evaluation.run_eval --task ... --run-id ... --judges ... --parallel 1
```

The judge runs only after complete solver metadata and bounded regular output files pass validation. Declared deliverables must be present; tasks without a deliverables map use discovered output files. Symlinks, changed source/package/input/output bytes, changed output membership, wrong task/model/run identities, incomplete solver runs, and malformed or inconsistent score rows are rejected. The optional reasoning effort is passed directly to the native solver.

## Results and evidence limits

Only `public/` is intended for sharing. `public/scores.json` contains the exact source and interpreter identity, solver/judge/settings, safe task/run IDs, per-criterion boolean verdicts, artifact digests, the native binary all-pass score, and a separately labeled criterion pass rate. `public/NOTICE.txt` includes upstream license credit. Raw task rubrics, model transcripts, generated documents, evaluator reasoning, and stdout/stderr remain under `private/`; do not submit that directory as a public package.

The bridge checks the public record before writing it. This does not automatically submit or promote it through the existing community publication workflow. A credential-free probe, synthetic process-contract tests, an offline judge stub against a real checkout, and a real sandbox startup are useful integration checks, but none proves a paid solver/judge baseline. Issue #48 remains open until a contributor-funded one-task solver/judge run succeeds and its actual public package is validated.

For local integration tests, set `LAB_CORE_ROOT` and `LAB_CORE_PYTHON` and run `uv run pytest -q tests/test_harvey_lab_core.py`. Set `LAB_CORE_SANDBOX_IMAGE` to a prepared immutable image ID to include the real rootless sandbox test. These tests never grant provider credentials; without the explicit local resources, the corresponding integration tests skip.

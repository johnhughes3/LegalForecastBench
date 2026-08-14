# Community Contributor Guide

This is the script for a dedicated environment: install the package, probe an adapter, pick a task slice, run it, interrupt it, resume it, validate, and package. Community results are not official LegalForecastBench scores.

Use a machine you control. Do not copy credential stores, your home directory, raw transcripts, or private case files into the run directory or a pull request.

## 1. Dedicated environment

Python 3.14 or newer is required. Create a directory that is not your daily checkout and clone the public repository:

```bash
git clone https://github.com/johnhughes3/LegalForecastBench.git
cd LegalForecastBench
uv sync --frozen
```

The current package version is `0.1.0a3` (`v0.1.0-alpha.3`). Use the revision that contains this guide — a later tag once one is cut, otherwise the `main` commit you cloned. Example adapter manifests live under `examples/adapters/`; they are not inside the published wheel. A source checkout is the supported install.

Confirm the CLI:

```bash
uv run legalforecast --help
uv run legalforecast multiharness --help
```

## 2. Capability probe

Start with a fixture adapter. It must not ask for credentials.

```bash
uv run legalforecast multiharness adapters inspect \
  --adapter-manifest examples/adapters/openai-responses/fixture-adapter-manifest.json \
  --output-dir tmp/multiharness/inspect

uv run legalforecast multiharness conformance \
  --adapter-manifest examples/adapters/openai-responses/fixture-adapter-manifest.json \
  --output-dir tmp/multiharness/conformance
```

`adapters inspect` writes the public manifest and capabilities. `conformance` is the no-provider suite. If either command asks for an API key, stop: you are not on `fixture-none`.

Other fixture manifests are listed in [docs/multiharness-adapter-spec.md](multiharness-adapter-spec.md).

## 3. Auth decision

Canonical profile IDs are hyphenated. Underscore aliases are refused.

| Profile | When to use it | Credentials |
| --- | --- | --- |
| `fixture-none` | Default for this walkthrough | None. The profile never reads keys. |
| `published-api-key` | Live provider call with an explicit key you supply | Contributor-funded. Not part of the fixture walkthrough. Requires spend authorization before anyone runs it here. |
| `contributor-subscription` | Local subscription login | Not supported yet. Do not attempt it from this guide. |

Write `fixture-none`, never `fixture_none`. A live `published-api-key` run is a separate, opt-in second leg. Do not put keys in the shell profile, in git, or in public JSON.

## 4. Task selection

Index tasks, then select a slice. A scoped run is labeled scoped. It is not a full-suite claim.

### LegalForecastBench fixture packets (zero credentials)

```bash
uv run legalforecast fixture e2e --output-dir tmp/fixture-run

uv run legalforecast multiharness tasks index \
  --suite lfb \
  --input tmp/fixture-run/packets.jsonl \
  --output tmp/multiharness/lfb-index.json
```

### Harvey LAB category

`--category` is the community name for a Harvey LAB module (`--module` is the same selector). You need a LAB checkout or a projected task folder. Harvey LAB is a separate Harvey AI corpus; keep its credit and license language if you publish anything that uses it.

```bash
uv run legalforecast multiharness tasks index \
  --suite harvey-lab \
  --lab-root "$HARVEY_LAB_ROOT" \
  --output tmp/multiharness/lab-index.json

uv run legalforecast multiharness tasks select \
  --index tmp/multiharness/lab-index.json \
  --category corporate \
  --output tmp/multiharness/lab-selection.json
```

### Explicit task list

```bash
uv run legalforecast multiharness tasks select \
  --index tmp/multiharness/lab-index.json \
  --task-id harvey_lab:corporate/merger \
  --output tmp/multiharness/id-selection.json
```

### Folder mode

Point the harness at a projected layout. The folder must contain `projection-manifest.json`. Each listed file is hashed; extra `task.json` / `task.md` / `prompt.txt` files and hash mismatches are refused. Absolute folder paths do not belong in public records.

```bash
uv run legalforecast multiharness tasks select \
  --index tmp/multiharness/lab-index.json \
  --task-folder path/to/projected-layout \
  --output tmp/multiharness/folder-selection.json
```

You can pass the same selectors on `multiharness run` instead of writing a selection file first.

## 5. Run, interrupt, resume

Fixture-first run over the LFB index (no credentials):

```bash
uv run legalforecast multiharness run \
  --task-index tmp/multiharness/lfb-index.json \
  --adapter-manifest examples/adapters/openai-responses/fixture-adapter-manifest.json \
  --model-key fixture-model \
  --output-dir tmp/multiharness/run \
  --run-id fixture-walkthrough
```

Category-scoped LAB run, once you have an index:

```bash
uv run legalforecast multiharness run \
  --task-index tmp/multiharness/lab-index.json \
  --category corporate \
  --adapter-manifest examples/adapters/openai-responses/fixture-adapter-manifest.json \
  --model-key fixture-model \
  --output-dir tmp/multiharness/run \
  --run-id corporate-walkthrough
```

Leave it running, then interrupt it with Ctrl-C (SIGINT) or SIGTERM. The in-flight task gets a terminal `interrupted` receipt, not a crash. Child processes are torn down. The command exits `130` and prints a resume hint. The run is a **partial** claim.

Resume with the same command plus `--resume`:

```bash
uv run legalforecast multiharness run \
  --task-index tmp/multiharness/lfb-index.json \
  --adapter-manifest examples/adapters/openai-responses/fixture-adapter-manifest.json \
  --model-key fixture-model \
  --output-dir tmp/multiharness/run \
  --run-id fixture-walkthrough \
  --resume
```

Completed tasks are skipped. Running `--resume` again after a finished run is a no-op. Resume **refuses** if the solver, config, runtime policy, or selection changed, or if `run-progress.json` is corrupt. The error names the drift. Do not delete the journal to “force” a continue.

## 6. Validate and package

```bash
uv run legalforecast multiharness community package \
  --run-dir tmp/multiharness/run \
  --conformance-report tmp/multiharness/conformance/conformance-report.json \
  --output-dir community/submissions/2026/your-submission \
  --submission-id your-submission \
  --submitter-name "Your Name" \
  --submitter-github your-handle \
  --run-operator-name "Your Name" \
  --adapter-author-name "Adapter Author or Team" \
  --task-source-credit-name "LegalForecastBench" \
  --benchmark-credit-name "LegalForecastBench" \
  --acknowledge-required-attestations \
  --hf-upload-plan

uv run legalforecast multiharness community validate-submission \
  --submission community/submissions/2026/your-submission/submission.json \
  --output tmp/community-validation.json
```

Open a pull request that adds only that submission directory. Details, attestations, and credits: [docs/community-submissions.md](community-submissions.md). Adapter contract: [docs/multiharness-adapter-spec.md](multiharness-adapter-spec.md).

## 7. Costs

`fixture-none` conformance and fixture runs do not call a provider. They should cost nothing beyond your machine.

A live `published-api-key` run is contributor-funded. Estimate tokens and USD from the model’s public price list *before* you run it, and do not start it without an explicit spend authorization if you are operating on shared credentials. LegalForecastBench does not pay community API bills.

## 8. Privacy

Keep private:

- API keys, subscription logins, Infisical paths, and `.env` files
- Hostnames, home directories, and absolute local paths
- Solver-visible source documents, transcripts, and `private-logs/`
- Sealed or non-public court files

Public JSON is scanned for secrets and path leakage. If a command’s output contains a key or a home path, you have a bug: stop and do not commit it.

## 9. Troubleshooting

| Symptom | What to do |
| --- | --- |
| Conformance or inspect asks for a key | You left `fixture-none`. Check the adapter’s `auth_profile_name`. |
| `fixture_none` / `published_api_key` rejected | Use hyphens: `fixture-none`, `published-api-key`. |
| Resume says solver, config, policy, or selection identity drifted | Re-run with the original adapter, model key, sandbox flags, and selectors. |
| Resume says the progress journal is corrupt | Do not hand-edit `run-progress.json`. Start a new `--output-dir`. |
| Folder mode refuses unrecognized or tampered bytes | Restore `projection-manifest.json` and the listed files. Extra `task.json` files are not ignored. |
| Exit `130` after Ctrl-C | Expected. Resume with the same command plus `--resume`. |
| Interrupted run labeled `full` | It is a partial claim. Do not delete the scoped or `partial` selection label. |
| Live profile path missing | Record that and stop. Do not fall back to keys already in your environment. |

`--help` on any subcommand is the next place to look after this page.

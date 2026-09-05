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

This file must exist after clone (`docs/community-contributor-guide.md`). If it is missing, you are on an older `main`; `git pull` and retry `uv sync --frozen`.

The current package version is `0.1.0a3` (`v0.1.0-alpha.3`). Use `main`, or a later tag once one is cut. Example adapter manifests live under `examples/adapters/`; they are not inside the published wheel. A source checkout is the supported install.

`uv` may warn that it could not hardlink across filesystems. That warning is harmless.

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

Successful commands print one `Wrote …` line on stderr. `adapters inspect` writes `adapter-capabilities.json`. `conformance` writes `conformance-report.json` with `"status": "passed"`. If either command asks for an API key, stop: you are not on `fixture-none`.

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

The quickest zero-credential path: no extra checkout, one packet. The Harvey LAB category below also works without credentials; it just needs the upstream corpus cloned first.

```bash
uv run legalforecast run issue-fixture --output-dir tmp/fixture-run
```

The fixture writes one packet per prediction unit under
`tmp/fixture-run/release/packets/`, alongside the `forecast-release.json` that
commits them. Index that release directly:

```bash
mkdir -p tmp/multiharness

uv run legalforecast multiharness tasks index \
  --suite lfb \
  --forecast-release tmp/fixture-run/release/forecast-release.json \
  --artifact-root tmp/fixture-run/release \
  --solver-input-root tmp/multiharness/lfb-solver-input \
  --output tmp/multiharness/lfb-index.json
```

That writes an index of three tasks, one per fixture prediction unit.
`--solver-input-root` is a private store of the exact solver-visible prompts;
keep it out of anything you publish. Its parent directory has to exist and the
store itself has to be absent, or indexing refuses with `solver input
destination must be fresh`; clear a previous one with `chmod -R u+w
tmp/multiharness/lfb-solver-input && rm -rf tmp/multiharness/lfb-solver-input`
before re-indexing.

### Harvey LAB category

`--category` is the community name for a Harvey LAB module (`--module` is the same selector). Harvey LAB is a separate Harvey AI corpus; keep its credit and license language if you publish anything that uses it.

A raw Harvey LAB git clone is **not** a contributor input. Upstream `task.json` files carry the evaluator's `criteria` — the graded answer. You project the corpus first: the projection splits each task into solver-visible bytes and an evaluator-private root, and the harness only ever indexes the projected side.

**Clone the pinned corpus, beside this checkout — not inside it.** The projection authenticates your checkout against a recorded commit, so fetch exactly that revision. A shallow fetch is enough: about 700 MB of working tree, roughly 15 seconds on a fast link.

```bash
cd ..                      # leave the LegalForecastBench checkout
git init harvey-labs && cd harvey-labs
git remote add origin https://github.com/harveyai/harvey-labs.git
git fetch --depth 1 origin 73feb91d63d53b1a44151d99329779c4defcdb72
git checkout FETCH_HEAD
cd ../LegalForecastBench   # back to this repository
```

Cloning it inside the benchmark checkout leaves a nested git repository and 700 MB of untracked files in your working tree, which is easy to commit by accident. The commands below assume the sibling layout and use `--lab-root ../harvey-labs`.

The pin lives in `legalforecast/multiharness/harvey_lab_projection.py` (`PINNED_COMMIT`). A checkout at any other revision, or one with local edits, is refused.

**Project a category.** Pick the two output directories yourself; both must not already exist.

```bash
uv run legalforecast multiharness tasks project \
  --lab-root ../harvey-labs \
  --category immigration \
  --output-dir tmp/lab/projected \
  --evaluator-private-dir tmp/lab/private
```

Stderr reports how many tasks projected, names every task it skipped and why, and prints the manifest path. The **`--evaluator-private-dir` holds the gold criteria**: never pass it to a solver, never put it in a pull request, and keep it outside the run directory.

The projection carries any number of declared `.docx` and `.xlsx` deliverables. When a legacy task declares none, bounded DOCX or XLSX files written under `output/` become the authenticated scored set, matching the pinned upstream evaluator's score-all-output behavior. Each criterion receives only the filenames it declares, with the authenticated full output set used only when the criterion omits that list. Other output formats remain unsupported and are skipped and listed; pass `--refuse-unsupported-tasks` if you would rather fail than accept a partial category. A projected category is a **scoped** run either way, never a full-suite claim.

Re-projecting into the same directory is refused, because projected files are sealed read-only and a stale tree would be silently reused. Remove the old one first:

```bash
chmod -R u+w tmp/lab/projected && rm -rf tmp/lab/projected
```

**Index and select.** Point `--projected-root` at what you just projected; every listed file is re-hashed before it is indexed.

```bash
uv run legalforecast multiharness tasks index \
  --suite harvey-lab \
  --projected-root tmp/lab/projected \
  --output tmp/multiharness/lab-index.json

uv run legalforecast multiharness tasks select \
  --index tmp/multiharness/lab-index.json \
  --category immigration \
  --output tmp/multiharness/lab-selection.json
```

`--lab-root` is the maintainer path: it reads the evaluator-private `task.json` directly. Pointing it at a projected layout tells you to use `--projected-root` instead.

### Explicit task list

```bash
uv run legalforecast multiharness tasks select \
  --index tmp/multiharness/lab-index.json \
  --task-id harvey_lab:immigration/draft-appeal-brief \
  --output tmp/multiharness/id-selection.json
```

`tasks project` takes the same `--task-id` selector (as an upstream path such as `immigration/draft-appeal-brief`) if you want to project a handful of tasks rather than a category.

### Folder mode

Folder mode accepts the projection root or any directory inside its `tasks/` tree. It authenticates the owning `harvey-lab-projection.v1.json`, re-hashes every listed file, and refuses bytes or task digests that do not match the index.

```bash
uv run legalforecast multiharness tasks select \
  --index tmp/multiharness/lab-index.json \
  --task-folder tmp/lab/projected/tasks/immigration \
  --output tmp/multiharness/folder-selection.json
```

You can pass the same selectors on `multiharness run` instead of writing a selection file first.

## 5. Run, interrupt, resume

Fixture-first run over the LFB index (no credentials):

```bash
uv run legalforecast multiharness run \
  --task-index tmp/multiharness/lfb-index.json \
  --solver-input-root tmp/multiharness/lfb-solver-input \
  --adapter-manifest examples/adapters/openai-responses/fixture-adapter-manifest.json \
  --model-key fixture-model \
  --output-dir tmp/multiharness/run \
  --run-id fixture-walkthrough
```

Stderr reports the run tally and the path of `run-progress.json`. Host process-group containment is the default; you do not pass `--host-process-containment` for this fixture. The bundled fixture adapter answers each of the three indexed units without credentials; that proves the harness path, not model quality.

Interrupt and remainder-only resume are for longer selections, which is what a LAB category gives you.

Category-scoped LAB run over the index you projected above:

```bash
uv run legalforecast multiharness run \
  --task-index tmp/multiharness/lab-index.json \
  --category immigration \
  --adapter-manifest examples/adapters/openai-responses/fixture-adapter-manifest.json \
  --model-key fixture-model \
  --output-dir tmp/multiharness/lab-run \
  --run-id immigration-walkthrough
```

The fixture adapter answers every task without calling a provider, so a category finishes in seconds. It does not write the task's deliverable, so a fixture LAB run proves the harness path, not model quality; there is no LAB score in it.

On a long run, interrupt with Ctrl-C (SIGINT) or SIGTERM. The in-flight task gets a terminal `interrupted` receipt, not a crash. Child processes are torn down. The command exits `130` and prints a resume hint. The run is a **partial** claim. Interrupting during startup, before the first task begins, is also an exit `130` with the same hint.

To see interrupt and resume actually do something, pick a category big enough to take a while. With the fixture adapter each task finishes in well under a second, so `immigration` (19 projected tasks) is usually over before you can reach for Ctrl-C; `corporate-ma` (123 projected tasks) gives you room.

Resume with the same command plus `--resume`:

```bash
uv run legalforecast multiharness run \
  --task-index tmp/multiharness/lfb-index.json \
  --solver-input-root tmp/multiharness/lfb-solver-input \
  --adapter-manifest examples/adapters/openai-responses/fixture-adapter-manifest.json \
  --model-key fixture-model \
  --output-dir tmp/multiharness/run \
  --run-id fixture-walkthrough \
  --resume
```

Completed tasks are skipped. Running `--resume` again after a finished run is a no-op. Resume **refuses** if the solver, config, runtime policy, or selection changed, or if `run-progress.json` is corrupt. The error names the drift. Do not delete the journal to “force” a continue.

## 6. Validate and package

Replace the placeholder names with yours before you open a pull request.

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

Stderr reports each `Wrote …` path. `tmp/community-validation.json` has `"status": "passed"`.

`--task-source-credit-name` names whoever the tasks came from, which is **not** always this project: for a Harvey LAB run it is `Harvey LAB`. `--benchmark-credit-name` stays `LegalForecastBench`. Only the submitter, operator, and adapter-author names are yours to fill in.

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
- Harvey LAB evaluator `criteria` and gold answers

Public JSON is scanned for secrets and path leakage. If a command’s output contains a key or a home path, you have a bug: stop and do not commit it.

## 9. Troubleshooting

| Symptom | What to do |
| --- | --- |
| This guide is missing after `git clone` | You cloned an older `main`. Check out the pull request that added the guide. |
| Conformance or inspect asks for a key | You left `fixture-none`. Check the adapter’s `auth_profile_name`. |
| `fixture_none` / `published_api_key` rejected | Use hyphens: `fixture-none`, `published-api-key`. |
| `--category` says this index has no Harvey LAB modules | You pointed `--category` at the LFB fixture index. Use that index without `--category`, or a projected LAB index. |
| `tasks project` says the LAB source does not match the recorded pin | Fetch the pinned commit and check it out; a dirty or ignored file also counts as drift. |
| `tasks project` says the output dir already exists | Projected files are sealed read-only: `chmod -R u+w <dir> && rm -rf <dir>`, then re-project. |
| `tasks project` skipped tasks in my category | A task declares an output other than DOCX or XLSX. The list on stderr names each one. The run is scoped. |
| `tasks project` says the category was not found | It lists the categories your checkout actually has. Category names are upstream directory names under `tasks/`. |
| `tasks index --lab-root` says to use `--projected-root` | You pointed the maintainer flag at a projected layout. Use `--projected-root`. |
| `--lab-root` fails on a raw Harvey LAB clone | The raw path reads evaluator `criteria`; it is not a contributor input. Project the corpus first. |
| Folder mode refuses a projected layout | Re-index the same projected root and do not modify its sealed files; folder mode refuses projection or index digest drift. |
| Ctrl-C does nothing on the fixture walkthrough | The one-task fixture finishes in about a second. That is expected. Use a large LAB category to exercise interrupt and resume. |
| I want a live provider run instead of `fixture-none` | The profile comes from the adapter manifest's `auth_profile_name`, not a CLI flag ([#853](https://github.com/johnhughes3/LegalForecastBench/issues/853)). Copy a manifest that lists `published-api-key` in `supported_auth_profiles` and set that field in your copy. |
| Resume says solver, config, policy, or selection identity drifted | Re-run with the original adapter, model key, sandbox flags, and selectors. |
| Resume says the progress journal is corrupt | Do not hand-edit `run-progress.json`. Start a new `--output-dir`. |
| Exit `130` after Ctrl-C | Expected. Resume with the same command plus `--resume`. |
| Interrupted run labeled `full` | It is a partial claim. Do not delete the scoped or `partial` selection label. |
| Live profile path missing | Record that and stop. Do not fall back to keys already in your environment. |

`--help` on any subcommand is the next place to look after this page.

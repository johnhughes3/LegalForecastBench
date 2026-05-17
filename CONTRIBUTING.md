# Contributing

LegalForecast-MTD is a pre-data alpha. The most useful contributions right now
are issue reports, reproducibility checks, and methodology feedback.

## Useful Feedback

Good reports include:

- the exact command you ran;
- whether the run used only fixtures or live credentials;
- the observed output or error;
- the expected behavior;
- the commit SHA.

Especially useful issues:

- a clean-checkout command fails;
- a public doc overstates the current benchmark state;
- a fixture artifact is missing provenance;
- a result-tier or leaderboard claim sounds canonical when it is not;
- a live or paid path can run without explicit opt-in.

## Local Checks

Run these before filing a release-blocking issue when practical:

```bash
uv sync
uv run legalforecast fixture e2e --output-dir tmp/fixture-run
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

The full release candidate gate is:

```bash
uv run scripts/alpha_release_check.py
```

Default checks must not require live credentials, model-provider credentials, or
paid services.

## Live Services

Do not run live Case.dev, PACER, CourtListener/RECAP, or model-provider calls
unless you intend to use those accounts. Read [docs/acquisition.md](docs/acquisition.md)
first.

Do not include API keys, provider account IDs, sealed filings, restricted
filings, or private source-document text in public issues, logs, screenshots,
or result submissions.

## Pull Requests

Pull requests are welcome as concrete examples, but they may be reimplemented
before merge. Keep patches small and include the command output needed to
review the change.
